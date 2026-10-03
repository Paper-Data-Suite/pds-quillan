"""Installed exact-wheel acceptance for Quillan Issue #417."""

from __future__ import annotations

import argparse
import builtins
from contextlib import redirect_stdout
import importlib
import importlib.metadata as metadata
import inspect
import io
import json
from pathlib import Path
import re
from typing import Any

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)
from pypdf import PdfReader

from quillan.assignment_reporting_packet import export_assignment_reporting_packet
from quillan.menu_navigation import (
    QuitQuillan,
    ReturnToMainMenu,
    print_navigation_options,
)
import quillan.review_menu as review_menu
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "issue417_installed_class"
ASSIGNMENT_ID = "issue417_installed_assignment"
STUDENT_ID = "00107"
MISSING_STUDENT_ID = "00208"
STANDARD_ID = "synthetic:W.REPORT.1"
TIMESTAMP = "2026-10-03T15:00:00+00:00"
PRIVATE_NOTE = "PRIVATE TEACHER NOTE MUST NOT LEAK"
PRIVATE_RATIONALE = "PRIVATE RATING RATIONALE MUST NOT LEAK"
BOM = b"\xef\xbb\xbf"


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"{module_name} has no import origin")
    return Path(raw).resolve()


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Résumé Evidence Report",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Synthetic prompt that must not leak into reporting.",
        "standards_profile_id": "synthetic_report_profile",
        "focus_standard_ids": [STANDARD_ID],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "synthetic_scale",
            "levels": [
                {"value": 1, "label": "Starting", "description": "Synthetic level."},
                {"value": 2, "label": "Growing", "description": "Synthetic level."},
                {"value": 3, "label": "Secure", "description": "Synthetic level."},
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _prepare_workspace(workspace: Path) -> None:
    if workspace.exists() and any(workspace.iterdir()):
        raise AssertionError("Issue #417 installed acceptance workspace must be empty")
    workspace.mkdir(parents=True, exist_ok=True)
    write_class_roster(
        workspace,
        create_roster(
            CLASS_ID,
            (
                {
                    "student_id": STUDENT_ID,
                    "last_name": "Álvarez",
                    "first_name": "Zoë",
                    "period": "3",
                },
                {
                    "student_id": MISSING_STUDENT_ID,
                    "last_name": "Missing",
                    "first_name": "Synthetic",
                    "period": "3",
                },
            ),
        ),
    )
    write_workspace_standards_library(
        workspace,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.REPORT.1",
                    source="SYNTHETIC",
                    short_name="Evidence — Integration",
                    description="Use synthetic evidence clearly.",
                    subject="English Language Arts",
                    course="Synthetic",
                    domain="Writing",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_report_profile",
                    standards=(STANDARD_ID,),
                    subject="English Language Arts",
                    course="Synthetic",
                    source="SYNTHETIC",
                    title="Synthetic Reporting Profile",
                ),
            ),
        ),
    )
    assignment_path = (
        workspace / "classes" / CLASS_ID / "modules" / "quillan"
        / "work" / ASSIGNMENT_ID / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True, exist_ok=True)
    assignment_path.write_text(
        json.dumps(_assignment(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    review["review_state"] = "ratings_complete"
    review["updated_at"] = TIMESTAMP
    review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": TIMESTAMP,
    }
    review["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_ID,
            "rating": 3,
            "rationale": PRIVATE_RATIONALE,
            "include_in_feedback": True,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    review["private_notes"] = [
        {
            "private_note_id": "private_note_0001",
            "text": PRIVATE_NOTE,
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _exercise_reporting(workspace: Path) -> dict[str, object]:
    before = _snapshot_files(workspace)
    result = export_assignment_reporting_packet(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        generated_at=TIMESTAMP,
    )
    prefix = f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/exports/"
    expected_relatives = {
        prefix + "student_performance_summary.csv",
        prefix + "class_summary.csv",
        prefix + "standards_summary.csv",
        prefix + "assignment_review_report.pdf",
        prefix + "assignment_results_manifest.json",
    }
    if set(result.relative_paths) != expected_relatives:
        raise AssertionError(f"unexpected reporting packet paths: {result.relative_paths}")

    after = _snapshot_files(workspace)
    for relative, original in before.items():
        if after.get(relative) != original:
            raise AssertionError(f"reporting mutated canonical source: {relative}")
    if set(after) - set(before) != expected_relatives:
        raise AssertionError("reporting packet created unexpected files")

    csv_paths = (
        result.student_performance_summary.summary_path,
        result.class_summary.summary_path,
        result.standards_summary.summary_path,
    )
    csv_texts: list[str] = []
    for path in csv_paths:
        data = path.read_bytes()
        if not data.startswith(BOM) or data[len(BOM):].startswith(BOM):
            raise AssertionError(f"CSV does not have exactly one leading UTF-8 BOM: {path}")
        text = data.decode("utf-8-sig")
        if text.startswith("\ufeff"):
            raise AssertionError(f"CSV logical header retained BOM text: {path}")
        csv_texts.append(text)

    student_csv = csv_texts[0]
    if "Zoë Álvarez" not in student_csv:
        raise AssertionError("Unicode student name did not survive CSV export")
    if "W.REPORT.1 — Evidence — Integration" not in student_csv:
        raise AssertionError("Unicode standard header did not survive CSV export")
    if "â€”" in student_csv:
        raise AssertionError("CSV contains mojibake")

    pdf_text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(str(result.assignment_review_report.report_path)).pages
    )
    if "Assignment Review Report" not in pdf_text:
        raise AssertionError("installed PDF report is unreadable")
    if "Résumé Evidence Report" not in pdf_text:
        raise AssertionError("installed PDF lost assignment title")

    manifest_text = result.assignment_results_manifest.manifest_path.read_text(
        encoding="utf-8"
    )
    manifest = json.loads(manifest_text)
    if manifest.get("record_type") != "assignment_results_manifest":
        raise AssertionError("installed JSON report has wrong record type")
    inventory = {
        item["artifact"]: item["status"]
        for item in manifest["generated_artifacts"]
    }
    expected_inventory = {
        "student_performance_summary_csv": "present",
        "class_summary_csv": "present",
        "standards_summary_csv": "present",
        "assignment_review_report_pdf": "present",
        "assignment_results_manifest_json": "generated",
    }
    if inventory != expected_inventory:
        raise AssertionError(f"unexpected generated-artifact inventory: {inventory}")

    public_reporting = "\n".join((*csv_texts, pdf_text, manifest_text))
    for private in (PRIVATE_NOTE, PRIVATE_RATIONALE, _assignment()["student_prompt"]):
        if private in public_reporting:
            raise AssertionError("private/non-reportable content leaked into reporting")

    return {
        "reporting_packet_files": sorted(expected_relatives),
        "single_snapshot_timestamp": result.generated_at,
        "csv_utf8_bom": True,
        "unicode_round_trip": True,
        "pdf_readable": True,
        "json_inventory_complete": True,
        "canonical_source_mutations": 0,
        "private_content_leaks": 0,
    }


def _exercise_navigation() -> dict[str, object]:
    source = inspect.getsource(review_menu)
    if re.search(r'print\("\d+\. Back"\)', source):
        raise AssertionError("installed review menu still displays numbered Back")
    if 'print("B. Back")' in source:
        raise AssertionError("installed review menu bypasses shared navigation printer")
    if "print_navigation_options()" not in source:
        raise AssertionError("installed review menu does not use shared navigation printer")

    rendered = io.StringIO()
    with redirect_stdout(rendered):
        print_navigation_options()
    if rendered.getvalue().splitlines() != ["B. Back", "M. Main Menu", "Q. Quit"]:
        raise AssertionError("installed shared navigation rendering changed")

    original_input = builtins.input
    try:
        builtins.input = lambda _prompt="": "b"
        if review_menu._prompt_confirm_review_action() is not False:
            raise AssertionError("B did not cancel/back out safely")

        builtins.input = lambda _prompt="": "m"
        try:
            review_menu._prompt_confirm_review_action()
        except ReturnToMainMenu:
            pass
        else:
            raise AssertionError("M did not propagate ReturnToMainMenu")

        builtins.input = lambda _prompt="": "q"
        try:
            review_menu._prompt_confirm_review_action()
        except QuitQuillan:
            pass
        else:
            raise AssertionError("Q did not propagate QuitQuillan")
    finally:
        builtins.input = original_input

    return {
        "numbered_back_entries": 0,
        "shared_navigation_rendering": ["B. Back", "M. Main Menu", "Q. Quit"],
        "back_signal": "safe return",
        "main_menu_signal": "propagated",
        "quit_signal": "propagated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-quillan-version", required=True)
    parser.add_argument("--expected-core-version", required=True)
    args = parser.parse_args()

    repository = args.repository.resolve(strict=True)
    if metadata.version("quillan") != args.expected_quillan_version:
        raise AssertionError("installed Quillan version mismatch")
    if metadata.version("pds-core") != args.expected_core_version:
        raise AssertionError("installed Core version mismatch")
    for module_name in (
        "quillan",
        "quillan.assignment_reporting_packet",
        "quillan.review_menu",
        "pds_core",
    ):
        if _module_origin(module_name).is_relative_to(repository):
            raise AssertionError(f"{module_name} import is source-shadowed")

    workspace = args.workspace.resolve()
    _prepare_workspace(workspace)
    result = {
        "status": "PASS",
        "quillan_version": args.expected_quillan_version,
        "core_version": args.expected_core_version,
        **_exercise_reporting(workspace),
        "navigation": _exercise_navigation(),
    }
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""End-to-end smoke test for the v0.8.0 scan/review/export workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.assignment_workflows import (
    build_assignment_config,
    write_assignment_config,
)
from quillan.cli import main
import quillan.cli_app.handlers.exports as exports_handler
import quillan.cli_app.handlers.review as review_handler
import quillan.cli_app.handlers.routing as routing_handler
import quillan.cli_app.handlers.submissions as submissions_handler
from quillan.review_record_paths import review_record_path
from quillan.submission_manifest_paths import submission_manifest_path

CLASS_ID = "english12_p3_v080"
ASSIGNMENT_ID = "argument_essay_v080"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
STANDARD_ID = "njsls-ela:W.AW.11-12.1"

@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create an isolated synthetic workspace for the v0.8.0 smoke test."""
    monkeypatch.setenv("PDS_WORKSPACE_ROOT", str(tmp_path))
    _patch_workspace_resolution(monkeypatch, tmp_path)

    _write_roster(tmp_path)
    _write_assignment(tmp_path)
    _write_standards_library(tmp_path)
    return tmp_path


def _patch_workspace_resolution(
    monkeypatch: pytest.MonkeyPatch,
    workspace_root: Path,
) -> None:
    """Route CLI handler workspace resolution into the temporary workspace."""
    for module in (
        exports_handler,
        review_handler,
        routing_handler,
        submissions_handler,
    ):
        monkeypatch.setattr(
            module,
            "resolve_workspace_root",
            lambda: workspace_root,
            raising=False,
        )

def _write_roster(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    class_dir.mkdir(parents=True, exist_ok=True)

    roster_path = class_dir / "roster.csv"
    with roster_path.open("w", encoding="utf-8", newline="") as roster_file:
        writer = csv.DictWriter(
            roster_file,
            fieldnames=(
                "class_id",
                "student_id",
                "last_name",
                "first_name",
                "period",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "3",
            }
        )
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": SECOND_STUDENT_ID,
                "last_name": "Patel",
                "first_name": "Mina",
                "period": "3",
            }
        )


def _write_assignment(root: Path) -> Path:
    assignment = build_assignment_config(
        assignment_id=ASSIGNMENT_ID,
        title="Synthetic Argument Essay",
        class_id=CLASS_ID,
        writing_type="argument",
        student_prompt="Write an argument using claims, reasoning, and evidence.",
        standards_profile_id="synthetic_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        basic_requirements={"paragraphs_min": 1},
        minimum_requirement_policy={
            "allow_return_without_full_review": True,
        },
    )
    return write_assignment_config(root, CLASS_ID, assignment)


def _write_standards_library(root: Path) -> None:
    write_workspace_standards_library(
        root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.AW.11-12.1",
                    source="NJSLS",
                    short_name="Argument Writing",
                    description="Use claims, reasoning, and evidence.",
                    subject="English Language Arts",
                    course="English 12",
                    domain="Writing",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_profile",
                    standards=(STANDARD_ID,),
                    subject="English Language Arts",
                    course="English 12",
                    source="NJSLS",
                    title="Synthetic Profile",
                ),
            ),
        ),
    )

def _response_payload(*, student_id: str = STUDENT_ID, page: int = 1) -> str:
    return (
        "PDS1|module=quillan|doc=response|"
        f"class={CLASS_ID}|aid={ASSIGNMENT_ID}|"
        f"sid={student_id}|page={page}"
    )

def _source_scan(root: Path) -> Path:
    source_path = root / "incoming" / "avery_argument_response.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"%PDF-1.4\n% synthetic response scan\n%%EOF\n")
    return source_path

def test_v080_scan_review_export_end_to_end_smoke(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the integrated v0.8.0 teacher-controlled workflow path."""
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
    assert assignment_path.is_file()


    assert main(["validate-assignment", str(assignment_path)]) == 0

    source_path = _source_scan(workspace)
    assert main(
        [
            "route-scan",
            str(source_path),
            "--payload",
            _response_payload(),
        ]
    ) == 0

    routed_files = sorted(
        (
            workspace
            / "classes"
            / CLASS_ID
            / "modules"
            / "quillan"
            / "work"
            / ASSIGNMENT_ID
            / "scans"
        ).glob("response_*.pdf")
    )
    assert len(routed_files) == 1
    assert not list(workspace.rglob("review.json"))
    assert not list(workspace.rglob("submission.json"))

    assert main(
        [
            "assemble-submissions",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--expected-pages",
            "1",
        ]
    ) == 0

    manifest_path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["submission_state"] == "unreviewed"
    assert manifest["expected_pages"] == 1
    assert manifest["pages"][0]["page_state"] == "present"

    selected_evidence_id = manifest["pages"][0]["selected_evidence_id"]
    assert isinstance(selected_evidence_id, str)
    assert selected_evidence_id

    assert main(
        [
            "list-submissions",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--expected-pages",
            "1",
        ]
    ) == 0

    assert main(
        [
            "add-note",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--text",
            "Teacher observation: the claim is clear.",
        ]
    ) == 0

    for removed_command in ("add-tag", "add-comment", "set-score"):
        with pytest.raises(SystemExit) as error:
            main([removed_command, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID])
        assert error.value.code != 0

    assert main(
        [
            "set-review-state",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        ]
    ) == 0

    review_path = review_record_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    assert review_path.is_file()

    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["review_state"] == "not_started"
    assert review["private_notes"][0]["text"] == "Teacher observation: the claim is clear."
    assert "notes" not in review
    assert "tags" not in review
    assert "comments" not in review
    assert "scores" not in review

    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated_manifest["submission_state"] == "reviewed"

    assert main(
        [
            "export-feedback",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        ]
    ) == 0
    assert main(["export-class-summary", CLASS_ID, ASSIGNMENT_ID]) == 0
    assert main(["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    class_summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "class_summary.csv"
    )
    standards_summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "exports"
        / "standards_summary.csv"
    )

    assert feedback_path.is_file()
    assert class_summary_path.is_file()
    assert standards_summary_path.is_file()

    feedback_text = feedback_path.read_text(encoding="utf-8")
    assert f"Assignment: {ASSIGNMENT_ID}" in feedback_text
    assert "Teacher Notes" not in feedback_text
    assert "No Focus Standard feedback selected." in feedback_text

    class_summary_text = class_summary_path.read_text(encoding="utf-8")
    assert STUDENT_ID in class_summary_text
    assert "not_started" in class_summary_text

    standards_summary_text = standards_summary_path.read_text(encoding="utf-8")
    assert "students_expected" in standards_summary_text
    assert STANDARD_ID in standards_summary_text

    output = capsys.readouterr().out
    assert "Routed Quillan response page." in output
    assert "Exported student feedback:" in output
    assert "Exported assignment-local class summary:" in output
    assert "Exported assignment-local Focus Standard summary:" in output

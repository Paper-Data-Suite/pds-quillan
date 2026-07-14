"""Synthetic end-to-end smoke test for the direct review CLI lifecycle."""

from __future__ import annotations

import builtins
import csv
import json
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from quillan.assignment_workflows import build_assignment_config, write_assignment_config
from quillan.cli import main
import quillan.cli_app.handlers.exports as exports_handler
import quillan.cli_app.handlers.feedback as feedback_handler
import quillan.cli_app.handlers.observations as observations_handler
import quillan.cli_app.handlers.ratings as ratings_handler
import quillan.cli_app.handlers.requirements as requirements_handler
import quillan.cli_app.handlers.review_status as review_status_handler
import quillan.cli_app.handlers.review_units as review_units_handler
from quillan.plain_paper_submission import (
    PLAIN_PAPER_ENTRY_METHOD,
    PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS,
    PLAIN_PAPER_WORKFLOW,
    is_plain_paper_submission,
)
from quillan.review_record import load_review_record
from quillan.review_record_paths import review_record_path
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)


CLASS_ID = "english10_p2_synthetic"
ASSIGNMENT_ID = "cli_lifecycle_synthetic"
STUDENT_ID = "00107"
STANDARD_ID = "synthetic:W.1"
RATING = "2"
PROMPT = "PRIVATE SYNTHETIC STUDENT PROMPT"
OBSERVATION_RATIONALE = "PRIVATE SYNTHETIC OBSERVATION RATIONALE"
OVERALL_RATIONALE = "PRIVATE SYNTHETIC OVERALL RATIONALE"
CUSTOM_COMMENT = "PRIVATE SYNTHETIC TEACHER FEEDBACK"
TIMESTAMP = "2026-07-13T12:00:00+00:00"


def _patch_workspace_resolution(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    for module in (
        requirements_handler,
        review_units_handler,
        observations_handler,
        ratings_handler,
        feedback_handler,
        exports_handler,
        review_status_handler,
    ):
        monkeypatch.setattr(module, "resolve_workspace_root", lambda: workspace)


def _write_roster(workspace: Path) -> Path:
    path = workspace / "classes" / CLASS_ID / "roster.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("class_id", "student_id", "last_name", "first_name", "period"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "2",
            }
        )
    return path


def _write_assignment(workspace: Path) -> Path:
    assignment = build_assignment_config(
        assignment_id=ASSIGNMENT_ID,
        title="Synthetic CLI Lifecycle Essay",
        class_id=CLASS_ID,
        writing_type="argument",
        student_prompt=PROMPT,
        standards_profile_id="synthetic_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "synthetic_two_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."},
                {"value": 2, "label": "Meeting", "description": "Meeting."},
            ],
        },
        basic_requirements={"paragraphs_min": 1},
        minimum_requirement_policy={"allow_return_without_full_review": True},
        created_at=TIMESTAMP,
    )
    return write_assignment_config(workspace, CLASS_ID, assignment)


def _write_plain_paper_manifest(workspace: Path) -> Path:
    path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {
            "submission_entry_method": PLAIN_PAPER_ENTRY_METHOD,
            "physical_evidence_status": PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS,
            "created_by_workflow": PLAIN_PAPER_WORKFLOW,
        },
    }
    return write_submission_manifest(path, manifest)


def _snapshot_files(workspace: Path) -> dict[str, bytes]:
    return {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }


def _review(workspace: Path) -> dict[str, Any]:
    return load_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    )


def test_complete_review_lifecycle_uses_only_direct_noninteractive_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_workspace_resolution(monkeypatch, tmp_path)
    monkeypatch.setattr(
        builtins,
        "input",
        lambda *_args, **_kwargs: pytest.fail("direct lifecycle must not prompt"),
    )
    roster_path = _write_roster(tmp_path)
    assignment_path = _write_assignment(tmp_path)
    submission_path = _write_plain_paper_manifest(tmp_path)
    review_path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    assert submission_path.is_file()
    assert not review_path.exists()
    assert is_plain_paper_submission(load_submission_manifest(submission_path))
    immutable_before = {
        assignment_path: assignment_path.read_bytes(),
        roster_path: roster_path.read_bytes(),
        submission_path: submission_path.read_bytes(),
    }
    initial_files = set(_snapshot_files(tmp_path))
    identity = [CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    exit_results: list[int] = []

    def run(args: list[str]) -> str:
        capsys.readouterr()
        result = main(args)
        exit_results.append(result)
        output = capsys.readouterr().out
        assert result == 0, output
        return output

    run(["requirements", "set-check", *identity, "--requirement-key", "paragraphs_min", "--met", "true"])
    review = _review(tmp_path)
    assert review["review_state"] == "requirements_checked"
    assert review["minimum_requirement_checks"] == [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 1,
            "met": True,
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    ]

    run(["requirements", "set-outcome", *identity, "--outcome", "met"])
    review = _review(tmp_path)
    assert review["minimum_requirement_outcome"]["status"] == "met"
    assert review["minimum_requirement_outcome"]["returned_without_full_review"] is False

    run(["review-units", "set", *identity, "--count", "1"])
    review = _review(tmp_path)
    assert [unit["unit_id"] for unit in review["review_units"]] == ["paragraph_1"]
    assert review["review_units"][0]["standard_observations"] == []

    run(
        [
            "observations", "set", *identity,
            "--unit-id", "paragraph_1", "--standard-id", STANDARD_ID,
            "--applicable", "true", "--evidence-present", "true",
            "--rating", RATING, "--rationale", OBSERVATION_RATIONALE,
            "--include-in-feedback", "true",
        ]
    )
    review = _review(tmp_path)
    observation = review["review_units"][0]["standard_observations"][0]
    assert observation["observation_id"] == "observation_0001"
    assert review["review_state"] == "observations_in_progress"
    assert review["overall_standard_ratings"] == []

    run(["observations", "mark-complete", *identity, "--yes"])
    review = _review(tmp_path)
    assert review["review_state"] == "observations_complete"
    assert sum(len(unit["standard_observations"]) for unit in review["review_units"]) == 1
    assert review["review_units"][0]["standard_observations"][0] == observation

    run(
        [
            "ratings", "set", *identity, "--standard-id", STANDARD_ID,
            "--rating", RATING, "--rationale", OVERALL_RATIONALE,
            "--include-in-feedback", "true",
        ]
    )
    review = _review(tmp_path)
    assert len(review["overall_standard_ratings"]) == 1
    assert review["overall_standard_ratings"][0]["rating"] == int(RATING)
    assert observation["rating"] == int(RATING)

    run(["ratings", "mark-complete", *identity, "--yes"])
    review = _review(tmp_path)
    assert review["review_state"] == "ratings_complete"
    assert len(review["overall_standard_ratings"]) == 1

    run(
        [
            "feedback", "set-options", *identity, "--standard-id", STANDARD_ID,
            "--include-overall-rating", "true", "--include-overall-rationale", "true",
            "--observation-ids", "observation_0001",
        ]
    )
    run(
        [
            "feedback", "add-comment", *identity, "--standard-id", STANDARD_ID,
            "--text", CUSTOM_COMMENT, "--include-in-feedback", "true",
        ]
    )
    review = _review(tmp_path)
    standard_feedback = review["feedback"]["standard_feedback"]
    assert len(standard_feedback) == 1
    assert standard_feedback[0]["included_observation_ids"] == ["observation_0001"]
    assert len(standard_feedback[0]["comments"]) == 1
    assert standard_feedback[0]["comments"][0]["source"] == "custom"
    assert not (tmp_path / "comments").exists()

    run(["feedback", "mark-composed", *identity, "--yes"])
    review = _review(tmp_path)
    assert review["review_state"] == "feedback_composed"
    assert review["feedback"]["standard_feedback"] == standard_feedback

    run(["export-feedback", *identity, "--format", "pdf"])
    pdf_path = submission_path.parent / "exports" / "feedback.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert len(PdfReader(str(pdf_path)).pages) >= 1
    assert not (pdf_path.parent / "feedback.md").exists()
    review = _review(tmp_path)
    assert review["review_state"] == "exported"
    assert review["exports"]["feedback_pdf"] is not None
    assert review["exports"]["feedback_pdf"]["source_review_updated_at"] == review["updated_at"]

    for path, original in immutable_before.items():
        assert path.read_bytes() == original

    before_status = _snapshot_files(tmp_path)
    status_text = run(["review-status", *identity, "--format", "json"])
    status = json.loads(status_text)
    assert status["schema_version"] == "1"
    assert status["record_type"] == "quillan_student_review_status"
    submission = status["submission"]
    assert submission["status"] == "valid"
    assert submission["plain_paper"] is True
    assert submission["pages"]["total"] == 0
    assert submission["evidence"]["total"] == 0
    final_review = status["review"]
    assert final_review["status"] == "valid"
    assert final_review["state"] == "exported"
    assert final_review["progress"] == {
        "returned_without_full_review": False,
        "observations_complete": True,
        "ratings_complete": True,
        "feedback_composed": True,
        "ready_for_export": True,
        "exported": True,
    }
    minimum = final_review["minimum_requirements"]
    for key, expected in {
        "configured": 1, "stored": 1, "current": 1, "unchecked": 0,
        "met": 1, "unmet": 0, "outcome": "met",
    }.items():
        assert minimum[key] == expected
    assert final_review["review_units"]["total"] == 1
    assert final_review["review_units"]["with_observations"] == 1
    assert final_review["review_units"]["empty"] == 0
    for key in (
        "total", "applicable", "evidence_present", "with_rating", "with_rationale",
        "included_for_feedback", "configured_standards_represented",
    ):
        assert final_review["observations"][key] == 1
    for key, expected in {
        "configured": 1, "current": 1, "missing": 0,
        "included_in_feedback": 1, "with_rationale": 1,
    }.items():
        assert final_review["overall_ratings"][key] == expected
    for key, expected in {
        "current_records": 1, "missing_configured_records": 0,
        "selected_observation_references": 1, "include_overall_rating_records": 1,
        "include_overall_rationale_records": 1, "comments_total": 1,
        "comments_included": 1, "custom_comments": 1,
        "include_review_unit_observations": True,
        "include_overall_standard_ratings": True,
    }.items():
        assert final_review["feedback"][key] == expected
    pdf_status = final_review["exports"]["feedback_pdf"]
    assert pdf_status["metadata_present"] is True
    assert pdf_status["file_present"] is True
    assert pdf_status["status"] == "present"
    assert pdf_status["stale"] is False
    assert final_review["exports"]["summary"]["current"] == 1
    assert final_review["exports"]["summary"]["stale"] == 0
    assert final_review["exports"]["feedback_markdown"]["status"] == "missing"
    for warning in (
        "feedback_pdf_stale", "feedback_pdf_file_missing", "feedback_pdf_metadata_missing"
    ):
        assert warning not in status["warnings"]
    for private_text in (
        PROMPT, OBSERVATION_RATIONALE, OVERALL_RATIONALE, CUSTOM_COMMENT,
        "student writing", "private note", "reusable comment",
    ):
        assert private_text not in status_text
    assert _snapshot_files(tmp_path) == before_status

    final_files = set(_snapshot_files(tmp_path))
    assert final_files - initial_files == {
        review_path.relative_to(tmp_path).as_posix(),
        pdf_path.relative_to(tmp_path).as_posix(),
    }
    assert exit_results == [0] * 12
    assert not list(tmp_path.rglob("*.csv")) or list(tmp_path.rglob("*.csv")) == [roster_path]
    assert not list(tmp_path.rglob("feedback.md"))
    assert not list(tmp_path.rglob("*scan*"))
    assert not list(tmp_path.rglob("*evidence*"))

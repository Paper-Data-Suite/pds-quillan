from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from quillan.cli_app import parser as cli_parser
from quillan.cli_app.handlers import submissions as cli_submissions
from quillan.cli_app.main import main
from quillan.plain_paper_submission import (
    PlainPaperSubmissionError,
    create_plain_paper_submission,
)
from quillan.review_record import load_review_record
import quillan.review_menu as review_menu
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_status import list_assignment_submission_status

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "literary_analysis"
STUDENT_ID = "stu_001"
TIMESTAMP = "2026-07-12T12:30:00-04:00"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    class_dir = tmp_path / "classes" / CLASS_ID
    assignment_dir = class_dir / "modules" / "quillan" / "work" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)
    with (class_dir / "roster.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("class_id", "student_id", "last_name", "first_name", "period"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Johnson",
                "first_name": "Mack",
                "period": "2",
            }
        )
    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Literary Analysis",
        "class_ids": [CLASS_ID],
        "writing_type": "analysis",
        "student_prompt": "Analyze the text.",
        "standards_profile_id": "ela",
        "focus_standard_ids": ["W.9"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "two_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."}
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment), encoding="utf-8"
    )
    return tmp_path


def test_creates_valid_evidence_less_manifest_and_empty_review(workspace: Path) -> None:
    created = create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    manifest = load_submission_manifest(created.submission_manifest_path)
    assert manifest == {
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
            "submission_entry_method": "plain_paper_manual",
            "physical_evidence_status": "teacher_has_external_plain_paper",
            "created_by_workflow": "plain_paper_submission",
        },
    }
    review = load_review_record(created.review_record_path)
    assert review["schema_version"] == "2"
    assert review["submission_manifest_path"] == created.submission_manifest_relative_path
    assert review["review_state"] == "not_started"
    assert review["review_units"] == []
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []
    assert review["private_notes"] == []
    assert review["module_details"] == {
        "review_entry_method": "plain_paper_manual",
        "created_by_workflow": "plain_paper_submission",
    }
    assert {path.name for path in created.submission_manifest_path.parent.iterdir()} == {
        "submission.json",
        "review.json",
    }


def test_rejects_student_not_in_roster(workspace: Path) -> None:
    with pytest.raises(PlainPaperSubmissionError, match="not in the roster"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, "stu_999", created_at=TIMESTAMP
        )


def test_does_not_overwrite_existing_submission(workspace: Path) -> None:
    created = create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    original = created.submission_manifest_path.read_bytes()

    with pytest.raises(PlainPaperSubmissionError, match="already exists"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    assert created.submission_manifest_path.read_bytes() == original


def test_rejects_orphan_review_without_writing_manifest(workspace: Path) -> None:
    student_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
    )
    student_dir.mkdir(parents=True)
    review_path = student_dir / "review.json"
    review_path.write_text("existing review", encoding="utf-8")

    with pytest.raises(PlainPaperSubmissionError, match="without a submission"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    assert review_path.read_text(encoding="utf-8") == "existing review"
    assert not (student_dir / "submission.json").exists()


def test_status_and_evidence_opening_are_teacher_friendly(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    status = list_assignment_submission_status(workspace, CLASS_ID, ASSIGNMENT_ID)

    assert review_menu._student_status_label(status.student_statuses[0]) == (
        "plain-paper manual submission; no digital evidence"
    )
    review_menu._open_submission_evidence(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    output = capsys.readouterr().out
    assert "No digital evidence is attached" in output
    assert "Review the physical paper" in output


def test_cli_help_lists_plain_paper_command_and_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--help"])
    assert "create-plain-paper-submission" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="0"):
        main(["create-plain-paper-submission", "--help"])
    output = capsys.readouterr().out
    assert "class_id" in output
    assert "assignment_id" in output
    assert "student_id" in output
    assert "--yes" in output
    assert "--dry-run" in output


@pytest.fixture
def cli_workspace(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    monkeypatch.setattr(cli_submissions, "resolve_workspace_root", lambda: workspace)
    return workspace


def test_cli_creates_plain_paper_submission(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--yes",
        ]
    )

    assert result == 0
    student_dir = (
        cli_workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
    )
    manifest = load_submission_manifest(student_dir / "submission.json")
    review = load_review_record(student_dir / "review.json")
    assert manifest["pages"] == []
    assert manifest["expected_pages"] is None
    assert manifest["module_details"]["submission_entry_method"] == (
        "plain_paper_manual"
    )
    assert review["schema_version"] == "2"
    assert review["module_details"]["review_entry_method"] == "plain_paper_manual"
    assert {path.name for path in student_dir.iterdir()} == {
        "submission.json",
        "review.json",
    }
    output = capsys.readouterr().out
    assert "Created plain-paper submission:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Submission manifest: classes/" in output
    assert "Review record: classes/" in output


def test_cli_dry_run_validates_without_writing(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--dry-run",
        ]
    )

    assert result == 0
    assert not (cli_workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "submissions").exists()
    output = capsys.readouterr().out
    assert "Plain-paper submission dry run:" in output
    assert "Would create submission manifest: classes/" in output
    assert "Would create review record: classes/" in output
    assert "No files were written." in output


def test_cli_requires_confirmation_without_writing(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = main(
        ["create-plain-paper-submission", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    )

    assert result == 1
    assert "requires --yes or --dry-run" in capsys.readouterr().out
    assert not (cli_workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "submissions").exists()


def test_cli_flags_are_mutually_exclusive() -> None:
    parser = cli_parser.build_parser()
    with pytest.raises(SystemExit, match="2"):
        parser.parse_args(
            [
                "create-plain-paper-submission",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--yes",
                "--dry-run",
            ]
        )


@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_rejects_invalid_student(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
    dry_run: bool,
) -> None:
    flag = "--dry-run" if dry_run else "--yes"
    result = main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            "stu_999",
            flag,
        ]
    )

    assert result == 1
    assert "not in the roster" in capsys.readouterr().out
    assert not (cli_workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "submissions").exists()


def test_cli_refuses_existing_manifest_without_changing_it(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    created = create_plain_paper_submission(
        cli_workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    original = created.submission_manifest_path.read_bytes()

    assert main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--yes",
        ]
    ) == 1
    assert created.submission_manifest_path.read_bytes() == original
    assert "already exists" in capsys.readouterr().out


def test_cli_refuses_orphan_review_without_changing_it(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    student_dir = cli_workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "submissions" / STUDENT_ID
    student_dir.mkdir(parents=True)
    review_path = student_dir / "review.json"
    review_path.write_bytes(b"existing review")

    assert main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--yes",
        ]
    ) == 1
    assert review_path.read_bytes() == b"existing review"
    assert not (student_dir / "submission.json").exists()
    assert "without a submission manifest" in capsys.readouterr().out


def test_cli_workspace_error_is_reported_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_workspace() -> Path:
        raise RuntimeError("workspace unavailable")

    monkeypatch.setattr(cli_submissions, "resolve_workspace_root", fail_workspace)
    result = main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--yes",
        ]
    )

    assert result == 1
    assert capsys.readouterr().out == (
        "Error: plain-paper submission was not created: workspace unavailable\n"
    )


def test_cli_rejects_class_not_in_assignment(
    cli_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assignment_path = (
        cli_workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment["class_ids"] = ["english10_p3"]
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")

    result = main(
        [
            "create-plain-paper-submission",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--yes",
        ]
    )

    assert result == 1
    assert "is not included in assignment" in capsys.readouterr().out
    assert not (
        cli_workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "submissions"
    ).exists()

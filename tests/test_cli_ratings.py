"""Direct CLI coverage for teacher-entered overall Focus Standard ratings."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import ratings as handlers
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "argument_01"
STUDENT_ID = "00107"
TIMESTAMP = "2026-07-13T12:00:00+00:00"


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Argument",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Make an argument.",
        "standards_profile_id": "ela",
        "focus_standard_ids": ["W.1", "L.2"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "unusual",
            "levels": [
                {"value": -2, "label": "Beginning", "description": "Beginning."},
                {"value": 0, "label": "Developing", "description": "Developing."},
                {"value": 7, "label": "Secure", "description": "Secure."},
            ],
        },
        "basic_requirements": {},
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
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {"submission_entry_method": "plain_paper_manual"},
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    assignment_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True)
    assignment_path.write_text(json.dumps(_assignment()), encoding="utf-8")
    write_submission_manifest(
        submission_manifest_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _write_review(workspace: Path) -> Path:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(
        path,
        build_empty_review_record(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id=STUDENT_ID,
            created_at=TIMESTAMP,
        ),
    )
    return path


def _set_args(*extra: str) -> list[str]:
    return [
        "ratings",
        "set",
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "--standard-id",
        "W.1",
        "--rating",
        "7",
        "--include-in-feedback",
        "false",
        *extra,
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["ratings", "--help"],
        ["ratings", "list", "--help"],
        ["ratings", "set", "--help"],
        ["ratings", "mark-complete", "--help"],
    ],
)
def test_ratings_help_exits_successfully(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 0


def test_bare_namespace_prints_help_without_resolving_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        handlers,
        "resolve_workspace_root",
        lambda: pytest.fail("bare ratings namespace resolved workspace"),
    )
    assert main(["ratings"]) == 0
    assert "{list,set,mark-complete}" in capsys.readouterr().out


def test_list_without_review_is_ordered_and_strictly_read_only(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = assignment_path.read_bytes(), manifest_path.read_bytes()

    assert main(["ratings", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = capsys.readouterr().out
    assert f"Student: {STUDENT_ID}" in output
    assert "Review state: not_started" in output
    assert "Review record exists: no" in output
    assert "Overall ratings complete: no" in output
    assert "Ratings recorded: 0" in output
    assert "Ratings missing: 2" in output
    assert output.index("- -2: Beginning") < output.index("- 0: Developing")
    assert output.index("Focus Standard: W.1") < output.index("Focus Standard: L.2")
    assert output.count("Overall rating: not rated") == 2
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == before


def test_set_creates_then_replaces_without_inference_or_duplicate(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_review(workspace)
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    immutable = assignment_path.read_bytes(), manifest_path.read_bytes()
    monkeypatch.setattr("builtins.input", lambda *_args: pytest.fail("CLI prompted"))

    assert main(_set_args("--rationale", "  Teacher judgment.  ")) == 0
    output = capsys.readouterr().out
    assert "Rating: 7 - Secure" in output
    assert "Rationale: present" in output
    assert "Include in feedback: no" in output
    assert "Action: created" in output
    assert "No supporting observations" in output

    assert main(_set_args()) == 0
    review = json.loads(path.read_text(encoding="utf-8"))
    assert len(review["overall_standard_ratings"]) == 1
    assert review["overall_standard_ratings"][0]["rationale"] is None
    assert review["review_units"] == []
    assert review["feedback"]["standard_feedback"] == []
    assert "Action: updated" in capsys.readouterr().out
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == immutable


def test_write_commands_require_an_existing_review(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_set_args()) == 1
    assert "review record must exist" in capsys.readouterr().out
    assert main(
        ["ratings", "mark-complete", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "--yes"]
    ) == 1
    assert "review record must exist" in capsys.readouterr().out
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


@pytest.mark.parametrize("rating", ["-2", "0"])
def test_set_accepts_every_configured_unusual_integer(
    workspace: Path, rating: str
) -> None:
    _write_review(workspace)
    argv = _set_args()
    argv[argv.index("7")] = rating
    assert main(argv) == 0


def test_invalid_standard_and_rating_fail_without_writing(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_review(workspace)
    before = path.read_bytes()
    argv = _set_args()
    argv[argv.index("W.1")] = "CORE.BUT.NOT.CONFIGURED"
    assert main(argv) == 1
    assert "Valid Focus Standard IDs: W.1, L.2" in capsys.readouterr().out
    assert path.read_bytes() == before
    argv = _set_args()
    argv[argv.index("7")] = "5"
    assert main(argv) == 1
    assert "Allowed values: -2, 0, 7" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_mark_complete_requires_yes_and_allows_zero_ratings(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_review(workspace)
    before = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(["ratings", "mark-complete", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID])
    assert error.value.code == 2
    assert path.read_bytes() == before

    assert main(
        ["ratings", "mark-complete", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "--yes"]
    ) == 0
    review = json.loads(path.read_text(encoding="utf-8"))
    assert review["review_state"] == "ratings_complete"
    assert review["overall_standard_ratings"] == []
    output = capsys.readouterr().out
    assert "Ratings recorded: 0" in output
    assert "Missing ratings: 2" in output
    assert "none were created" in output


def test_returned_review_is_listable_but_byte_stable_for_failed_writes(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_review(workspace)
    review = json.loads(path.read_text(encoding="utf-8"))
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing work.",
        "updated_at": TIMESTAMP,
    }
    write_review_record(path, review, overwrite=True)
    before = path.read_bytes()

    assert main(["ratings", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    assert "overall ratings not applicable" in capsys.readouterr().out
    assert main(_set_args()) == 1
    assert "returned without full standards review" in capsys.readouterr().out
    assert main(
        ["ratings", "mark-complete", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "--yes"]
    ) == 1
    assert path.read_bytes() == before


def test_list_reports_stale_rating_without_counting_it(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_review(workspace)
    review = json.loads(path.read_text(encoding="utf-8"))
    review["overall_standard_ratings"] = [
        {
            "standard_id": "STALE.9",
            "rating": 7,
            "rationale": None,
            "include_in_feedback": False,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    write_review_record(path, review, overwrite=True)
    before = copy.deepcopy(path.read_bytes())

    assert main(["ratings", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    output = capsys.readouterr().out
    assert "Ratings recorded: 0" in output
    assert "Ratings missing: 2" in output
    assert "Unrecognized or stale stored ratings" in output
    assert "STALE.9: 7" in output
    assert path.read_bytes() == before

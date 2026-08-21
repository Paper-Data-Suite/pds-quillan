"""Issue #383 direct CLI tests for the deterministic review work queue."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.review_queue as cli_review_queue
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import _write_assignment, _write_roster


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_cli_review_queue_text_and_json_are_deterministic_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    before = _snapshot(tmp_path)
    monkeypatch.setattr(cli_review_queue, "resolve_workspace_root", lambda: tmp_path)

    assert main(["review-queue", CLASS_ID, ASSIGNMENT_ID]) == 0
    first_text = capsys.readouterr().out
    assert "Review Work Queue" in first_text
    assert "Avery Rivera (00100)" in first_text

    assert main(["review-queue", CLASS_ID, ASSIGNMENT_ID]) == 0
    assert capsys.readouterr().out == first_text

    assert (
        main(["review-queue", CLASS_ID, ASSIGNMENT_ID, "--format", "json"])
        == 0
    )
    document = json.loads(capsys.readouterr().out)

    assert document["schema_version"] == "1"
    assert document["record_type"] == "quillan_assignment_review_work_queue"
    assert document["class_id"] == CLASS_ID
    assert document["assignment_id"] == ASSIGNMENT_ID
    assert [student["student_id"] for student in document["students"]] == [
        "00100",
        "00200",
        "00900",
    ]
    assert document["counts"]["no_submission"] == 3
    assert sum(document["counts"].values()) == 3
    assert _snapshot(tmp_path) == before


def test_cli_review_queue_help_and_roster_failure_are_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["review-queue", "--help"])
    assert help_exit.value.code == 0
    help_output = capsys.readouterr().out
    assert "--format" in help_output
    assert "class_id" in help_output
    assert "assignment_id" in help_output

    _write_assignment(tmp_path)
    before = _snapshot(tmp_path)
    monkeypatch.setattr(cli_review_queue, "resolve_workspace_root", lambda: tmp_path)

    assert main(["review-queue", CLASS_ID, ASSIGNMENT_ID]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: could not build review work queue" in captured.err
    assert "roster is unavailable" in captured.err
    assert _snapshot(tmp_path) == before


def test_cli_review_queue_rejects_later_navigation_options() -> None:
    for option in ("--next", "--previous", "--priority", "--continue"):
        with pytest.raises(SystemExit) as exit_info:
            main(["review-queue", CLASS_ID, ASSIGNMENT_ID, option])
        assert exit_info.value.code == 2

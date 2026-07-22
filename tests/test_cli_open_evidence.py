"""CLI contract tests for identity-based evidence opening."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.submissions as cli_submissions
from quillan.submission_review_opening import (
    OpenedSubmissionEvidencePage,
    OpenedSubmissionReview,
)


def test_raw_path_open_evidence_command_is_retired(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["open-evidence", "classes/class_1/scans/evidence.pdf"])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid choice: 'open-evidence'" in captured.err


def test_open_submission_passes_explicit_evidence_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int | None, str | None]] = []
    opened = OpenedSubmissionReview(
        class_id="class_1",
        assignment_id="assignment_1",
        student_id="student_1",
        manifest_path=tmp_path / "submission.json",
        manifest_relative_path=(
            "classes/class_1/modules/quillan/work/assignment_1/"
            "submissions/student_1/submission.json"
        ),
        submission_state="unreviewed",
        opened_pages=(
            OpenedSubmissionEvidencePage(
                page_number=2,
                evidence_id="evidence_2",
                evidence_path=tmp_path / "evidence.pdf",
                evidence_relative_path="classes/class_1/scans/evidence.pdf",
                page_state="present",
            ),
        ),
    )
    monkeypatch.setattr(cli_submissions, "resolve_workspace_root", lambda: tmp_path)

    def open_submission(
        *_args: object,
        page_number: int | None = None,
        evidence_id: str | None = None,
    ) -> OpenedSubmissionReview:
        calls.append((page_number, evidence_id))
        return opened

    monkeypatch.setattr(
        cli_submissions, "open_student_submission_for_review", open_submission
    )

    assert main(
        [
            "open-submission",
            "class_1",
            "assignment_1",
            "student_1",
            "--page",
            "2",
            "--evidence-id",
            "evidence_2",
        ]
    ) == 0
    assert calls == [(2, "evidence_2")]
    output = capsys.readouterr().out
    assert "Evidence: evidence_2" in output
    assert str(tmp_path) not in output

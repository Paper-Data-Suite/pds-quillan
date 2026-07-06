"""CLI guardrails for removed reusable review-comment selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
from quillan.review_record_paths import review_record_path
from tests.test_review_comments import BANK_ID, _write_bank
from tests.test_review_scores import _write_manifest
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID


def test_cli_help_does_not_expose_add_comment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    assert error.value.code == 0
    assert "add-comment" not in capsys.readouterr().out


def test_cli_add_comment_is_removed_and_cannot_write_review_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(
            [
                "add-comment",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--bank",
                BANK_ID,
                "--comment-id",
                "evidence_needs_explanation",
            ]
        )

    assert error.value.code != 0
    assert "invalid choice" in capsys.readouterr().err
    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()

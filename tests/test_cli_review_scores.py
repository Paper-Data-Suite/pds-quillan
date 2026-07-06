"""CLI guardrails for removed criterion-score review writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
from quillan.review_record_paths import review_record_path
from tests.test_review_scores import _write_manifest
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID


def test_cli_help_does_not_expose_set_score(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    assert error.value.code == 0
    assert "set-score" not in capsys.readouterr().out


def test_cli_set_score_is_removed_and_cannot_write_review_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(
            [
                "set-score",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--criterion",
                "evidence",
                "--label",
                "Evidence",
                "--score",
                "3",
                "--max-score",
                "4",
            ]
        )

    assert error.value.code != 0
    assert "invalid choice" in capsys.readouterr().err
    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()

"""CLI guardrails for removed structured teacher review tags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
from quillan.review_record_paths import review_record_path
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID, _write_manifest


def test_cli_help_does_not_expose_add_tag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    assert error.value.code == 0
    assert "add-tag" not in capsys.readouterr().out


def test_cli_add_tag_is_removed_and_cannot_write_review_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(
            [
                "add-tag",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "--label",
                "Evidence needs explanation",
                "--polarity",
                "developing",
            ]
        )

    assert error.value.code != 0
    assert "invalid choice" in capsys.readouterr().err
    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    manifests = list(tmp_path.rglob("submission.json"))
    assert len(manifests) == 1
    assert json.loads(manifests[0].read_text(encoding="utf-8"))["student_id"] == STUDENT_ID

"""Issue #415 direct CLI coverage for the immutable inbox projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.resubmission_inbox as cli_inbox
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _write_assignment


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_cli_resubmission_inbox_text_json_and_help_are_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_assignment(tmp_path)
    before = _snapshot(tmp_path)
    monkeypatch.setattr(cli_inbox, "resolve_workspace_root", lambda: tmp_path)

    assert main(["resubmission-inbox", CLASS_ID, ASSIGNMENT_ID]) == 0
    assert "Resubmission / Rescan Review" in capsys.readouterr().out

    assert (
        main(
            [
                "resubmission-inbox",
                CLASS_ID,
                ASSIGNMENT_ID,
                "--format",
                "json",
            ]
        )
        == 0
    )
    document = json.loads(capsys.readouterr().out)
    assert document["schema_version"] == "1"
    assert document["record_type"] == "quillan_assignment_resubmission_inbox"
    assert document["items"] == []
    assert _snapshot(tmp_path) == before

    with pytest.raises(SystemExit) as help_exit:
        main(["resubmission-inbox", "--help"])
    assert help_exit.value.code == 0
    assert "--format" in capsys.readouterr().out

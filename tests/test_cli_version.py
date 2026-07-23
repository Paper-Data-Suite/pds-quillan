"""Release-version CLI contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli_app.parser import build_parser


def test_version_is_exact_stdout_only_and_workspace_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sentinel = tmp_path / "workspace-must-not-exist"
    monkeypatch.setenv("PDS_WORKSPACE_ROOT", str(sentinel))
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(["--version"])
    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == "quillan 0.8.9\n"
    assert captured.err == ""
    assert not sentinel.exists()

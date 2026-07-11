"""Menu tests for teacher-facing Quillan scan review resolution."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.review_menu as review_menu
from tests.test_scan_review_resolution import _write_failure


def _inputs(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> None:
    responses: Iterator[str] = iter(values)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(responses)
        except StopIteration as error:
            raise AssertionError("Menu requested unexpected input.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def test_menu_resolves_one_scan_review_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure_path = _write_failure(tmp_path)
    before = failure_path.read_bytes()
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        ["2", "r", "1", "", "1", "", "", "", "3", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Resolve Scan Review Items" in output
    assert "No QR payload was found." in output
    assert "Scan review item resolved." in output
    assert "scans/review/resolutions/" in output
    assert failure_path.read_bytes() == before
    assert "archive" not in output.casefold()


def test_menu_scan_review_empty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["2", "r", "", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "There are no unresolved or deferred scan review items." in output
    assert not (tmp_path / "scans").exists()
    assert "archive" not in output.casefold()

"""Issue #417 Slice 5 tests for the Assignment Reports menu surface."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Iterator

import pytest

import quillan.review_menu as review_menu
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID


def _inputs(values: list[str]) -> Iterator[str]:
    return iter(values)


def test_assignment_reports_menu_lists_packet_pdf_and_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = _inputs(["B"])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": next(answers),
    )

    review_menu._menu_export_assignment_reports(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    for expected in (
        "Assignment Reports",
        "1. Generate reporting packet",
        "2. Comprehensive Class Summary",
        "3. Focus Standard Summary",
        "4. Student Performance Summary",
        "5. Assignment Review PDF",
        "6. Assignment Results JSON",
        "B. Back",
    ):
        assert expected in output


def test_assignment_reports_menu_dispatches_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, str, str]] = []

    def fake_packet(root: Path, class_id: str, assignment_id: str) -> None:
        calls.append((root, class_id, assignment_id))

    answers = _inputs(["1", "", "B"])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": next(answers),
    )
    monkeypatch.setattr(
        review_menu,
        "_menu_export_reporting_packet",
        fake_packet,
    )

    review_menu._menu_export_assignment_reports(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert calls == [(tmp_path, CLASS_ID, ASSIGNMENT_ID)]

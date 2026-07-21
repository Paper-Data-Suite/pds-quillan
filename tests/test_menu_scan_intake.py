from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import quillan.cli_app.handlers.routing as routing
import quillan.menu as menu


def _inputs(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> None:
    iterator: Iterator[str] = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


def test_menu_selects_real_inbox_scan_through_shared_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "scans_inbox"
    inbox.mkdir()
    scan = inbox / "teacher.png"
    scan.write_bytes(b"scan")
    calls: list[tuple[Path, Path, bool]] = []

    def run(
        source_path: Path,
        workspace_root: Path,
        *,
        on_summary: object = None,
    ) -> int:
        calls.append((source_path, workspace_root, on_summary is not None))
        return 1

    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_qr_scan_intake", run)
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr(menu, "pause_for_user", lambda: None)
    _inputs(monkeypatch, ["1", "b"])
    menu.launch_scan_intake_workflow()
    assert calls == [(scan, tmp_path, True)]


def test_menu_custom_path_uses_same_service_without_post_route_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom = tmp_path / "custom.pdf"
    custom.write_bytes(b"scan")
    calls: list[tuple[Path, bool]] = []

    def run(
        source_path: Path,
        _workspace_root: Path,
        *,
        on_summary: object = None,
    ) -> int:
        calls.append((source_path, on_summary is not None))
        return 1

    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_qr_scan_intake", run)
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr(menu, "pause_for_user", lambda: None)
    _inputs(monkeypatch, ["c", f'"{custom}"', "b"])
    menu.launch_scan_intake_workflow()
    assert calls == [(custom, False)]

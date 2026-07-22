from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

import quillan.cli_app.handlers.routing as routing
import quillan.menu as menu
from quillan.intake_assembly import PostDispatchReviewPreservationBatch
from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen
from tests.test_observation_result_models import _models


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
    result = object()
    calls: list[tuple[Path, Path]] = []
    routed_results: list[object] = []

    def run(
        source_path: Path,
        workspace_root: Path,
    ) -> object:
        calls.append((source_path, workspace_root))
        return result

    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_scan_intake_workflow", run)
    monkeypatch.setattr(
        menu,
        "handle_scan_post_route_menu",
        lambda _root, value: routed_results.append(value),
    )
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr(menu, "pause_for_user", lambda: None)
    _inputs(monkeypatch, ["1", "b"])
    menu.launch_scan_intake_workflow()
    assert calls == [(scan, tmp_path)]
    assert routed_results == [result]


def test_menu_custom_path_uses_same_service_without_post_route_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom = tmp_path / "custom.pdf"
    custom.write_bytes(b"scan")
    result = object()
    calls: list[Path] = []
    routed_results: list[object] = []

    def run(
        source_path: Path,
        _workspace_root: Path,
    ) -> object:
        calls.append(source_path)
        return result

    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_scan_intake_workflow", run)
    monkeypatch.setattr(
        menu,
        "handle_scan_post_route_menu",
        lambda _root, value: routed_results.append(value),
    )
    monkeypatch.setattr(menu, "clear_screen", lambda: None)
    monkeypatch.setattr(menu, "pause_for_user", lambda: None)
    _inputs(monkeypatch, ["c", f'"{custom}"', "b"])
    menu.launch_scan_intake_workflow()
    assert calls == [custom]
    assert routed_results == [result]


@pytest.mark.menu_density_workflow("complete scan intake")
def test_complete_scan_intake_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inbox = tmp_path / "scans_inbox"
    inbox.mkdir()
    scan = inbox / "teacher.png"
    scan.write_bytes(b"scan")
    post = _models(tmp_path)[-1]
    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_scan_intake_workflow", lambda *_args: post)
    recorder = MenuScreenRecorder(["1", "b", "b"])
    recorder.install(monkeypatch)

    menu.launch_scan_intake_workflow()

    screens = recorder.screens(capsys.readouterr().out)
    assert_focused_child_screen(
        screens,
        heading="Processing Scan Intake",
        required_text="Source:",
        forbidden_parent_text="C. Choose custom file/folder path",
        parent_heading="Scan Intake / Route Paper Responses",
        result_heading="Scan Intake Result",
        unrelated_previous_text="Available scans:",
    )


@pytest.mark.menu_density_workflow("partial scan intake")
def test_partial_scan_intake_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    custom = tmp_path / "partial.pdf"
    custom.write_bytes(b"scan")
    post = _models(tmp_path)[-1]
    partial = replace(
        post,
        review_preservation=PostDispatchReviewPreservationBatch(
            failures=("preservation failed",)
        ),
    )
    monkeypatch.setattr(routing, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(routing, "run_scan_intake_workflow", lambda *_args: partial)
    recorder = MenuScreenRecorder(["c", str(custom), "b", "b"])
    recorder.install(monkeypatch)

    menu.launch_scan_intake_workflow()

    screens = recorder.screens(capsys.readouterr().out)
    assert_focused_child_screen(
        screens,
        heading="Processing Scan Intake",
        required_text=str(custom),
        forbidden_parent_text="C. Choose custom file/folder path",
        parent_heading="Scan Intake / Route Paper Responses",
        result_heading="Outcome: partial failure",
        unrelated_previous_text="No supported scans found",
    )

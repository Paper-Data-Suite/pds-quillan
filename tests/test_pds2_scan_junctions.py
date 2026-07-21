"""Real Windows junction boundaries for retained PDS2 intake."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pytest
from pds_core.module_profiles import ModuleProfile, ModuleRegistry
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan

import quillan.pds2_scan_intake as intake
from quillan.module_errors import QuillanScanPreflightError, QuillanSourcePageError
from quillan.retained_scan_pages import retained_source_page_count


def _handler(*_args: object) -> object:
    return object()


def _registry() -> ModuleRegistry:
    return ModuleRegistry((ModuleProfile(
        "quillan", "Quillan", frozenset({"1"}), frozenset({"PDS2"}),
        frozenset({"1"}), frozenset({"active"}), _handler,
    ),))


def _make_junction(link: Path, target: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows junction coverage runs only on Windows.")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(
            "junction creation unavailable: "
            f"{completed.stdout.strip()} {completed.stderr.strip()}"
        )


def _write_image(path: Path) -> None:
    assert cv2.imwrite(
        str(path), np.full((10, 10, 3), 255, dtype=np.uint8)
    )


def test_workspace_root_junction_is_rejected_before_retention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace-target"
    target.mkdir()
    junction = tmp_path / "workspace-junction"
    _make_junction(junction, target)
    source = tmp_path / "scan.png"
    _write_image(source)
    monkeypatch.setattr(
        intake,
        "retain_source_scan",
        lambda *_args, **_kwargs: pytest.fail("unsafe workspace must not retain"),
    )
    try:
        result = intake.process_quillan_scan_source(
            source, workspace_root=junction, registry=_registry()
        )
        assert result.retained_source is None
        assert isinstance(result.source_error, QuillanScanPreflightError)
        assert not (target / "scans" / "review").exists()
    finally:
        os.rmdir(junction)


def test_selected_source_parent_junction_is_rejected_without_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "scan.png"
    _write_image(source)
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    junction = tmp_path / "linked-parent"
    _make_junction(junction, outside)
    monkeypatch.setattr(
        intake,
        "retain_source_scan",
        lambda *_args, **_kwargs: pytest.fail("junction source must not retain"),
    )
    try:
        result = intake.process_quillan_scan_source(
            junction / source.name, workspace_root=workspace, registry=_registry()
        )
        assert result.retained_source is None
        assert isinstance(result.source_error, QuillanScanPreflightError)
        assert sentinel.read_bytes() == b"unchanged"
        assert not (workspace / "scans" / "review").exists()
    finally:
        os.rmdir(junction)


def test_selected_folder_junction_is_rejected_without_external_traversal(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside-folder"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    junction = tmp_path / "folder-junction"
    _make_junction(junction, outside)
    try:
        with pytest.raises(QuillanScanPreflightError):
            intake.process_quillan_scan_folder(
                junction, workspace_root=workspace, registry=_registry()
            )
        assert sentinel.read_bytes() == b"unchanged"
        assert not (workspace / "scans").exists()
    finally:
        os.rmdir(junction)


def test_supported_junction_child_does_not_suppress_later_safe_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    folder = tmp_path / "folder"
    folder.mkdir()
    outside = tmp_path / "outside-child"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    unsafe = folder / "a.pdf"
    _make_junction(unsafe, outside)
    safe = folder / "b.png"
    _write_image(safe)
    real_retain = retain_source_scan
    retained_calls: list[Path] = []

    def retain(root: Path, source: Path) -> RetainedSourceScan:
        retained_calls.append(source)
        return real_retain(root, source)

    monkeypatch.setattr(intake, "retain_source_scan", retain)
    try:
        summary = intake.process_quillan_scan_folder(
            folder, workspace_root=workspace, registry=_registry()
        )
        assert len(summary.source_results) == 2
        assert summary.source_results[0].retained_source is None
        assert summary.source_results[1].retained_source is not None
        assert retained_calls == [safe]
        assert sentinel.read_bytes() == b"unchanged"
    finally:
        os.rmdir(unsafe)


def test_intermediate_retained_path_junction_is_rejected(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "scan.png"
    _write_image(source)
    retained = retain_source_scan(workspace, source)
    date_dir = retained.retained_source_path.parent
    outside = tmp_path / "outside-retained"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    moved = outside / retained.retained_source_path.name
    shutil.move(str(retained.retained_source_path), moved)
    date_dir.rmdir()
    _make_junction(date_dir, outside)
    try:
        with pytest.raises(QuillanSourcePageError):
            retained_source_page_count(retained, workspace_root=workspace)
        assert sentinel.read_bytes() == b"unchanged"
    finally:
        os.rmdir(date_dir)

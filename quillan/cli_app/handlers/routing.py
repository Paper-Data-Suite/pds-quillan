"""Thin CLI/menu facade for retained PDS2 scan intake."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root as _resolve_workspace_root

from quillan.pds2_scan_intake import (
    QuillanScanIntakeSummary,
    process_quillan_scan_folder,
    process_quillan_scan_source,
)
from quillan.intake_assembly import (
    format_post_dispatch_persistence_result,
    persist_and_assemble_quillan_scan_successes,
)
from quillan.retained_scan_pages import SUPPORTED_SCAN_EXTENSIONS
from quillan.scan_intake_summary import format_scan_intake_summary


def resolve_workspace_root() -> Path:
    return _resolve_workspace_root()


def handle_route_scan(args: argparse.Namespace) -> int:
    """Dispatch QR locators extracted from retained physical source pages."""
    return run_qr_scan_intake(args.source_file)


def run_qr_scan_intake(
    source_path: Path,
    workspace_root: Path | None = None,
    *,
    on_summary: Callable[[QuillanScanIntakeSummary], None] | None = None,
) -> int:
    """Delegate one file/folder operation to the reusable PDS2 service."""
    try:
        root = resolve_workspace_root() if workspace_root is None else workspace_root
        if source_path.exists() and source_path.is_dir():
            summary = process_quillan_scan_folder(source_path, workspace_root=root)
        else:
            source = process_quillan_scan_source(source_path, workspace_root=root)
            summary = QuillanScanIntakeSummary(
                (source,), source.registry_module_ids
            )
    except WorkspaceRootError as error:
        print(f"Error: could not resolve the PDS workspace: {error}")
        return 1
    except Exception as error:
        print(f"Error: scan intake could not start safely: {error}")
        return 1
    print(format_scan_intake_summary(summary))
    try:
        post_dispatch = persist_and_assemble_quillan_scan_successes(root, summary)
    except Exception as error:
        print(f"Error: post-dispatch persistence could not start safely: {error}")
        if on_summary is not None:
            on_summary(summary)
        return 1
    print()
    print(format_post_dispatch_persistence_result(post_dispatch))
    if on_summary is not None:
        on_summary(summary)
    return 0 if post_dispatch.complete_success else 1


__all__ = [
    "SUPPORTED_SCAN_EXTENSIONS", "handle_route_scan", "resolve_workspace_root",
    "run_qr_scan_intake",
]

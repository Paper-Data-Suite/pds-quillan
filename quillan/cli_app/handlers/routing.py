"""Thin CLI/menu facade for retained PDS2 scan intake."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root as _resolve_workspace_root

from quillan.intake_assembly import (
    QuillanScanWorkflowResult,
    format_scan_workflow_result,
    process_quillan_scan_workflow,
)
from quillan.retained_scan_pages import SUPPORTED_SCAN_EXTENSIONS


def resolve_workspace_root() -> Path:
    return _resolve_workspace_root()


def handle_route_scan(args: argparse.Namespace) -> int:
    """Dispatch QR locators extracted from retained physical source pages."""
    try:
        result = run_scan_intake_workflow(args.source_file)
    except WorkspaceRootError as error:
        print(f"Error: could not resolve the PDS workspace: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Error: scan intake could not start safely: {error}", file=sys.stderr)
        return 1
    print(format_scan_workflow_result(result))
    return 0 if result.complete_success else 1


def run_scan_intake_workflow(
    source_path: Path,
    workspace_root: Path | None = None,
) -> QuillanScanWorkflowResult:
    """Return the typed result shared by direct and menu interfaces."""
    root = resolve_workspace_root() if workspace_root is None else workspace_root
    return process_quillan_scan_workflow(root, source_path)


def run_qr_scan_intake(
    source_path: Path,
    workspace_root: Path | None = None,
) -> int:
    """Render the shared typed workflow result for simple programmatic callers."""
    try:
        result = run_scan_intake_workflow(source_path, workspace_root)
    except WorkspaceRootError as error:
        print(f"Error: could not resolve the PDS workspace: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Error: scan intake could not start safely: {error}", file=sys.stderr)
        return 1
    print(format_scan_workflow_result(result))
    return 0 if result.complete_success else 1


__all__ = [
    "SUPPORTED_SCAN_EXTENSIONS", "handle_route_scan", "resolve_workspace_root",
    "run_qr_scan_intake", "run_scan_intake_workflow",
]

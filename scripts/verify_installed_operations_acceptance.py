"""Verify an installed Quillan module-operations provider outside source."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
from pathlib import Path

from pds_core.module_operations import (
    MODULE_OPERATIONS_ENTRY_POINT_GROUP,
    ModuleAttentionReport,
    ModuleOperationsRequest,
    invoke_module_attention,
    validate_module_operations_profile,
)
from pds_core.provider_diagnostics import (
    diagnose_core_providers,
    inspect_core_provider_entry_points,
)


def _resolved_module_file(module: object) -> Path:
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError("installed module has no import origin")
    path = Path(raw).resolve()
    if not path.is_file():
        raise AssertionError("installed module origin is not an ordinary file")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--expected-core-version", required=True)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    repository = args.repository.resolve()
    if not workspace.is_dir():
        parser.error("--workspace must be an existing directory")

    quillan_version = metadata.version("quillan")
    core_version = metadata.version("pds-core")
    if core_version != args.expected_core_version:
        raise AssertionError(
            f"expected Core {args.expected_core_version}, got {core_version}"
        )

    import quillan
    import pds_core

    quillan_origin = _resolved_module_file(quillan)
    core_origin = _resolved_module_file(pds_core)
    if quillan_origin.is_relative_to(repository):
        raise AssertionError("installed Quillan import is source-shadowed")
    if core_origin.is_relative_to(repository.parent / "pds-core"):
        raise AssertionError("installed Core import is source-shadowed")

    points = tuple(
        entry
        for entry in metadata.entry_points(group=MODULE_OPERATIONS_ENTRY_POINT_GROUP)
        if entry.name == "quillan"
    )
    if len(points) != 1:
        raise AssertionError(f"expected one Quillan operations entry point, got {len(points)}")
    point = points[0]
    expected_target = "quillan.pds_operations:get_module_operations_profile"
    if point.value != expected_target:
        raise AssertionError(f"unexpected operations provider target: {point.value}")

    provider = point.load()
    profile = validate_module_operations_profile(provider())
    if profile.module_id != "quillan":
        raise AssertionError("operations provider module identity is not quillan")
    if profile.attention_provider is None:
        raise AssertionError("Quillan attention provider is absent")
    if profile.readiness_provider is not None:
        raise AssertionError("Quillan readiness must remain absent until issue #392")

    inspected = tuple(
        row
        for row in inspect_core_provider_entry_points(provider_kind="module_operations")
        if row.entry_point_name == "quillan"
    )
    if len(inspected) != 1:
        raise AssertionError("Core metadata inspection did not find exactly one Quillan provider")

    diagnosed = tuple(
        row
        for row in diagnose_core_providers(provider_kind="module_operations")
        if row.metadata.entry_point_name == "quillan"
    )
    if len(diagnosed) != 1 or diagnosed[0].code != "provider.valid":
        raise AssertionError(f"Core provider diagnostics rejected Quillan: {diagnosed!r}")

    before = tuple(
        sorted(
            (
                path.relative_to(workspace).as_posix(),
                path.is_dir(),
                path.stat().st_size if path.is_file() else None,
            )
            for path in workspace.rglob("*")
        )
    )
    invocation = invoke_module_attention(
        profile,
        ModuleOperationsRequest(workspace_root=workspace),
    )
    if invocation.code != "module_operations.evaluated":
        raise AssertionError(f"empty installed-workspace attention failed: {invocation!r}")
    report = invocation.report
    if not isinstance(report, ModuleAttentionReport):
        raise AssertionError("installed attention invocation returned the wrong report type")
    if report.evaluation != "evaluated" or report.summaries:
        raise AssertionError("empty installed workspace must evaluate with zero summaries")

    after = tuple(
        sorted(
            (
                path.relative_to(workspace).as_posix(),
                path.is_dir(),
                path.stat().st_size if path.is_file() else None,
            )
            for path in workspace.rglob("*")
        )
    )
    if after != before:
        raise AssertionError("installed attention invocation modified the workspace")

    print(
        json.dumps(
            {
                "quillan_version": quillan_version,
                "core_version": core_version,
                "quillan_import": str(quillan_origin),
                "core_import": str(core_origin),
                "entry_point_group": MODULE_OPERATIONS_ENTRY_POINT_GROUP,
                "entry_point_target": point.value,
                "provider_diagnostic": diagnosed[0].code,
                "attention_invocation": invocation.code,
                "readiness_present": profile.readiness_provider is not None,
                "workspace_unchanged": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

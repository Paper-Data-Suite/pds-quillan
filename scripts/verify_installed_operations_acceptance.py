"""Verify an installed Quillan module-operations provider outside source."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
from pathlib import Path

from pds_core.classes import write_class_roster
from pds_core.module_operations import (
    MODULE_OPERATIONS_ENTRY_POINT_GROUP,
    ModuleAttentionReport,
    ModuleOperationsRequest,
    ModuleReadinessReport,
    invoke_module_attention,
    invoke_module_readiness,
    validate_module_operations_profile,
)
from pds_core.provider_diagnostics import (
    diagnose_core_providers,
    inspect_core_provider_entry_points,
)
from pds_core.rosters import ROSTER_REQUIRED_COLUMNS, Roster, StudentRecord


def _resolved_module_file(module: object) -> Path:
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError("installed module has no import origin")
    path = Path(raw).resolve()
    if not path.is_file():
        raise AssertionError("installed module origin is not an ordinary file")
    return path


def _inventory(root: Path) -> tuple[tuple[str, bool, int | None], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                path.is_dir(),
                path.stat().st_size if path.is_file() else None,
            )
            for path in root.rglob("*")
        )
    )


def _readiness_report(
    profile: object,
    request: ModuleOperationsRequest,
    *,
    expected_code: str,
    expected_ready: bool | None,
) -> ModuleReadinessReport:
    invocation = invoke_module_readiness(profile, request)  # type: ignore[arg-type]
    if invocation.code != expected_code:
        raise AssertionError(
            f"installed readiness returned {invocation.code!r}, "
            f"expected {expected_code!r}: {invocation!r}"
        )
    report = invocation.report
    if not isinstance(report, ModuleReadinessReport):
        raise AssertionError("installed readiness invocation returned the wrong report type")
    if report.ready is not expected_ready:
        raise AssertionError(
            f"installed readiness returned ready={report.ready!r}, "
            f"expected {expected_ready!r}"
        )
    return report


def _write_synthetic_class(workspace: Path, class_id: str) -> None:
    roster = Roster(
        class_id=class_id,
        students=(
            StudentRecord(
                class_id=class_id,
                student_id="synthetic_student",
                last_name="Example",
                first_name="Ada",
                period="1",
                extra_fields={},
            ),
        ),
        columns=ROSTER_REQUIRED_COLUMNS,
    )
    write_class_roster(workspace, roster)


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

    operations_points = tuple(
        entry
        for entry in metadata.entry_points(group=MODULE_OPERATIONS_ENTRY_POINT_GROUP)
        if entry.name == "quillan"
    )
    if len(operations_points) != 1:
        raise AssertionError(
            f"expected one Quillan operations entry point, got {len(operations_points)}"
        )
    point = operations_points[0]
    expected_target = "quillan.pds_operations:get_module_operations_profile"
    if point.value != expected_target:
        raise AssertionError(f"unexpected operations provider target: {point.value}")

    launcher_points = tuple(
        entry
        for entry in metadata.entry_points(group="console_scripts")
        if entry.name == "quillan"
    )
    if len(launcher_points) != 1:
        raise AssertionError(
            f"expected one installed Quillan console script, got {len(launcher_points)}"
        )
    launcher = launcher_points[0]
    if launcher.value != "quillan.cli:main":
        raise AssertionError(f"unexpected Quillan launcher target: {launcher.value}")

    provider = point.load()
    profile = validate_module_operations_profile(provider())
    if profile.module_id != "quillan":
        raise AssertionError("operations provider module identity is not quillan")
    if profile.attention_provider is None:
        raise AssertionError("Quillan attention provider is absent")
    if profile.readiness_provider is None:
        raise AssertionError("Quillan readiness provider is absent")

    inspected = tuple(
        row
        for row in inspect_core_provider_entry_points(provider_kind="module_operations")
        if row.entry_point_name == "quillan"
    )
    if len(inspected) != 1:
        raise AssertionError(
            "Core metadata inspection did not find exactly one Quillan provider"
        )

    diagnosed = tuple(
        row
        for row in diagnose_core_providers(provider_kind="module_operations")
        if row.metadata.entry_point_name == "quillan"
    )
    if len(diagnosed) != 1 or diagnosed[0].code != "provider.valid":
        raise AssertionError(f"Core provider diagnostics rejected Quillan: {diagnosed!r}")

    missing_workspace = workspace.parent / "issue392-missing-workspace"
    if missing_workspace.exists():
        raise AssertionError("installed readiness missing-workspace fixture already exists")
    missing_report = _readiness_report(
        profile,
        ModuleOperationsRequest(workspace_root=missing_workspace),
        expected_code="module_operations.evaluation_unavailable",
        expected_ready=None,
    )
    if missing_workspace.exists():
        raise AssertionError("readiness evaluation created the missing workspace")

    empty_before = _inventory(workspace)
    empty_report = _readiness_report(
        profile,
        ModuleOperationsRequest(workspace_root=workspace),
        expected_code="module_operations.evaluated",
        expected_ready=True,
    )
    attention_invocation = invoke_module_attention(
        profile,
        ModuleOperationsRequest(workspace_root=workspace),
    )
    empty_after = _inventory(workspace)
    if attention_invocation.code != "module_operations.evaluated":
        raise AssertionError(
            f"empty installed-workspace attention failed: {attention_invocation!r}"
        )
    attention_report = attention_invocation.report
    if not isinstance(attention_report, ModuleAttentionReport):
        raise AssertionError("installed attention invocation returned the wrong report type")
    if attention_report.evaluation != "evaluated" or attention_report.summaries:
        raise AssertionError("empty installed workspace must evaluate with zero summaries")
    if empty_after != empty_before:
        raise AssertionError("installed empty-workspace operations modified the workspace")

    class_id = "issue392_acceptance"
    _write_synthetic_class(workspace, class_id)
    class_before = _inventory(workspace)

    class_report = _readiness_report(
        profile,
        ModuleOperationsRequest(workspace_root=workspace, class_id=class_id),
        expected_code="module_operations.evaluated",
        expected_ready=True,
    )
    missing_class_report = _readiness_report(
        profile,
        ModuleOperationsRequest(
            workspace_root=workspace,
            class_id="issue392_missing_class",
        ),
        expected_code="module_operations.evaluated",
        expected_ready=False,
    )
    class_after = _inventory(workspace)
    if class_after != class_before:
        raise AssertionError("installed class readiness modified the workspace")

    print(
        json.dumps(
            {
                "quillan_version": quillan_version,
                "core_version": core_version,
                "quillan_import": str(quillan_origin),
                "core_import": str(core_origin),
                "entry_point_group": MODULE_OPERATIONS_ENTRY_POINT_GROUP,
                "entry_point_target": point.value,
                "launcher_target": launcher.value,
                "provider_diagnostic": diagnosed[0].code,
                "attention_invocation": attention_invocation.code,
                "readiness_present": profile.readiness_provider is not None,
                "readiness_missing_workspace": {
                    "evaluation": missing_report.evaluation,
                    "ready": missing_report.ready,
                },
                "readiness_empty_workspace": {
                    "evaluation": empty_report.evaluation,
                    "ready": empty_report.ready,
                },
                "readiness_valid_class": {
                    "evaluation": class_report.evaluation,
                    "ready": class_report.ready,
                },
                "readiness_missing_class": {
                    "evaluation": missing_class_report.evaluation,
                    "ready": missing_class_report.ready,
                },
                "workspace_unchanged_by_operations": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

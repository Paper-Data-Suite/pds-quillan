from __future__ import annotations

import importlib.metadata as metadata
from pathlib import Path

from pds_core.module_operations import (
    MODULE_OPERATIONS_ENTRY_POINT_GROUP,
    ModuleAttentionReport,
    ModuleOperationsRequest,
    invoke_module_attention,
)
from pds_core.provider_diagnostics import (
    diagnose_core_providers,
    inspect_core_provider_entry_points,
)

from quillan.pds_operations import get_module_operations_profile


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


def test_core_provider_diagnostics_accept_installed_quillan_operations_profile() -> None:
    points = tuple(
        entry
        for entry in metadata.entry_points(group=MODULE_OPERATIONS_ENTRY_POINT_GROUP)
        if entry.name == "quillan"
    )
    assert len(points) == 1
    assert points[0].value == "quillan.pds_operations:get_module_operations_profile"

    metadata_rows = tuple(
        row
        for row in inspect_core_provider_entry_points(provider_kind="module_operations")
        if row.entry_point_name == "quillan"
    )
    assert len(metadata_rows) == 1
    assert metadata_rows[0].entry_point_group == MODULE_OPERATIONS_ENTRY_POINT_GROUP

    diagnostics = tuple(
        row
        for row in diagnose_core_providers(provider_kind="module_operations")
        if row.metadata.entry_point_name == "quillan"
    )
    assert len(diagnostics) == 1
    result = diagnostics[0]
    assert result.code == "provider.valid"
    assert result.stage == "valid"
    assert result.declared_identity == "quillan"
    assert result.profile_validation == "passed"
    assert result.core_compatibility == "passed"
    assert result.registry_conflict is False
    assert result.validated_profile == get_module_operations_profile()


def test_provider_diagnostics_do_not_invoke_attention_or_create_workspace(
    tmp_path: Path,
) -> None:
    nonexistent = tmp_path / "must_not_exist"
    before = _inventory(tmp_path)
    diagnostics = tuple(
        row
        for row in diagnose_core_providers(provider_kind="module_operations")
        if row.metadata.entry_point_name == "quillan"
    )
    after = _inventory(tmp_path)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "provider.valid"
    assert before == after
    assert not nonexistent.exists()


def test_empty_workspace_attention_is_read_only_through_core_invocation(
    tmp_path: Path,
) -> None:
    before = _inventory(tmp_path)
    result = invoke_module_attention(
        get_module_operations_profile(),
        ModuleOperationsRequest(workspace_root=tmp_path),
    )
    after = _inventory(tmp_path)

    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleAttentionReport)
    assert result.report.evaluation == "evaluated"
    assert result.report.summaries == ()
    assert before == after


def test_readiness_is_present_after_issue392() -> None:
    profile = get_module_operations_profile()
    assert profile.readiness_provider is not None

from __future__ import annotations

from pathlib import Path

import pytest
from pds_core.module_operations import (
    MODULE_OPERATIONS_CONTRACT_VERSION,
    ModuleOperationsRequest,
    ModuleReadinessReport,
    invoke_module_readiness,
    validate_module_operations_profile,
)
from pds_core.rosters import RosterReadError

import quillan.readiness_provider as readiness
from quillan.pds_operations import (
    evaluate_quillan_attention,
    evaluate_quillan_readiness,
    get_module_operations_profile,
)
from quillan.work_paths import QuillanWorkPathError


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


def _write_roster(root: Path, class_id: str, *, roster_class_id: str | None = None) -> None:
    class_dir = root / "classes" / class_id
    class_dir.mkdir(parents=True)
    (class_dir / "roster.csv").write_text(
        "class_id,student_id,last_name,first_name,period\n"
        f"{roster_class_id or class_id},student_a,Example,Ada,1\n",
        encoding="utf-8",
    )


def test_profile_extends_existing_core_v1_profile_with_readiness() -> None:
    profile = get_module_operations_profile()
    assert validate_module_operations_profile(profile) == profile
    assert profile.module_id == "quillan"
    assert profile.supported_core_operations_contract_versions == frozenset(
        {MODULE_OPERATIONS_CONTRACT_VERSION}
    )
    assert profile.readiness_provider is evaluate_quillan_readiness
    assert profile.attention_provider is evaluate_quillan_attention


def test_readiness_rejects_non_request_values() -> None:
    with pytest.raises(TypeError, match="ModuleOperationsRequest"):
        readiness.evaluate_quillan_readiness(object())  # type: ignore[arg-type]


def test_missing_workspace_is_unavailable_through_core() -> None:
    result = invoke_module_readiness(
        get_module_operations_profile(),
        ModuleOperationsRequest(),
    )
    assert result.code == "module_operations.evaluation_unavailable"
    assert isinstance(result.report, ModuleReadinessReport)
    assert result.report.evaluation == "unavailable"
    assert result.report.ready is None
    assert tuple(notice.code for notice in result.report.notices) == (
        "quillan_readiness_unavailable",
    )


def test_empty_existing_workspace_is_ready_and_read_only(tmp_path: Path) -> None:
    before = _inventory(tmp_path)
    result = invoke_module_readiness(
        get_module_operations_profile(),
        ModuleOperationsRequest(workspace_root=tmp_path),
    )
    after = _inventory(tmp_path)

    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleReadinessReport)
    assert result.report.evaluation == "evaluated"
    assert result.report.ready is True
    assert result.report.notices == ()
    assert before == after == ()


def test_valid_exact_class_with_core_roster_is_ready_and_read_only(
    tmp_path: Path,
) -> None:
    _write_roster(tmp_path, "class_a")
    before = _inventory(tmp_path)
    result = invoke_module_readiness(
        get_module_operations_profile(),
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a"),
    )
    after = _inventory(tmp_path)

    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleReadinessReport)
    assert result.report.ready is True
    assert result.report.notices == ()
    assert before == after


def test_safe_missing_exact_class_is_evaluated_not_ready(tmp_path: Path) -> None:
    result = invoke_module_readiness(
        get_module_operations_profile(),
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a"),
    )
    assert result.code == "module_operations.evaluated"
    assert isinstance(result.report, ModuleReadinessReport)
    assert result.report.ready is False
    assert tuple(notice.code for notice in result.report.notices) == (
        "quillan_class_not_ready",
    )


def test_missing_roster_is_evaluated_not_ready(tmp_path: Path) -> None:
    (tmp_path / "classes" / "class_a").mkdir(parents=True)
    report = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a")
    )
    assert report.evaluation == "evaluated"
    assert report.ready is False
    assert tuple(notice.code for notice in report.notices) == (
        "quillan_class_not_ready",
    )


def test_invalid_core_roster_is_evaluated_not_ready(tmp_path: Path) -> None:
    _write_roster(tmp_path, "class_a", roster_class_id="class_b")
    report = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a")
    )
    assert report.evaluation == "evaluated"
    assert report.ready is False
    assert tuple(notice.code for notice in report.notices) == (
        "quillan_class_not_ready",
    )


def test_unsafe_quillan_work_chain_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path, "class_a")

    def fail_preflight(root: Path, class_id: str) -> Path:
        raise QuillanWorkPathError("synthetic unsafe path")

    monkeypatch.setattr(readiness, "preflight_quillan_work_collection", fail_preflight)
    report = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a")
    )
    assert report.evaluation == "unavailable"
    assert report.ready is None
    assert tuple(notice.code for notice in report.notices) == (
        "quillan_readiness_unavailable",
    )


def test_unreadable_core_roster_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path, "class_a")

    def fail_roster(root: Path, class_id: str) -> object:
        raise RosterReadError(root / "classes" / class_id / "roster.csv", "denied")

    monkeypatch.setattr(readiness, "load_class_roster", fail_roster)
    report = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(workspace_root=tmp_path, class_id="class_a")
    )
    assert report.evaluation == "unavailable"
    assert report.ready is None


def test_active_school_year_does_not_invent_quillan_readiness_state(
    tmp_path: Path,
) -> None:
    without_year = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(workspace_root=tmp_path)
    )
    with_year = readiness.evaluate_quillan_readiness(
        ModuleOperationsRequest(
            workspace_root=tmp_path,
            active_school_year="2026-2027",
        )
    )
    assert with_year == without_year

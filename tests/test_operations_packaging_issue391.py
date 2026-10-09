from __future__ import annotations

import inspect
import importlib.metadata as metadata
from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.version import Version
from pds_core.module_operations import (
    MODULE_OPERATIONS_ENTRY_POINT_GROUP,
    ModuleOperationsProfile,
    validate_module_operations_profile,
)

from quillan.pds_operations import get_module_operations_profile

ROOT = Path(__file__).resolve().parents[1]


def _project() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_current_quillan_requires_reader_metadata_core_release() -> None:
    project = _project()["project"]
    assert isinstance(project, dict)
    deps = project["dependencies"]
    assert isinstance(deps, list)
    values = [str(item) for item in deps if str(item).startswith("pds-core")]
    assert values == ["pds-core>=0.6.5,<0.7"]
    requirement = Requirement(values[0])
    assert Version("0.6.5") in requirement.specifier
    assert Version("0.6.4") not in requirement.specifier
    assert Version("0.7.0") not in requirement.specifier

def test_pyproject_declares_exact_operations_entry_point() -> None:
    project = _project()["project"]
    assert isinstance(project, dict)
    groups = project["entry-points"]
    assert isinstance(groups, dict)
    assert groups[MODULE_OPERATIONS_ENTRY_POINT_GROUP] == {
        "quillan": "quillan.pds_operations:get_module_operations_profile"
    }


def test_operations_provider_is_zero_argument_validated_core_v1_profile() -> None:
    assert tuple(inspect.signature(get_module_operations_profile).parameters) == ()
    profile = get_module_operations_profile()
    assert isinstance(profile, ModuleOperationsProfile)
    assert validate_module_operations_profile(profile) == profile
    assert profile.module_id == "quillan"
    assert profile.attention_provider is not None
    assert profile.readiness_provider is not None


def test_installed_operations_entry_point_resolves_exact_provider() -> None:
    points = tuple(
        metadata.entry_points().select(
            group=MODULE_OPERATIONS_ENTRY_POINT_GROUP,
            name="quillan",
        )
    )
    assert len(points) == 1
    point = points[0]
    assert point.value == "quillan.pds_operations:get_module_operations_profile"
    provider = point.load()
    assert tuple(inspect.signature(provider).parameters) == ()
    assert provider() == get_module_operations_profile()


def test_core_wheel_verifier_keeps_historical_and_current_contracts() -> None:
    from scripts.verify_core_wheel import CORE_WHEEL_CONTRACTS

    assert tuple(sorted(CORE_WHEEL_CONTRACTS)) == (
        "0.6.0", "0.6.2", "0.6.3", "0.6.4", "0.6.5"
    )
    assert CORE_WHEEL_CONTRACTS["0.6.4"].version == "0.6.4"
    assert CORE_WHEEL_CONTRACTS["0.6.5"].sha256 == "9ace75f17b23b7f0ed6a709d531af5120db43d0325b4148d26f2d6ba1d4b3c18"

def test_ci_uses_exact_core_065_and_no_historical_matrix() -> None:
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Download released Core 0.6.5" in source
    assert "--core-version 0.6.5" in source
    assert "core-063-qualification:" not in source
    assert "operations-wheel-qualification:" not in source
    assert "installed-wheel:" in source

def test_active_release_candidate_uses_core_065() -> None:
    source = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "'--core-version', '0.6.5'" in source
    assert "$PdsCore064Wheel" not in source

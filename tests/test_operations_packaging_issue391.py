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


def test_current_quillan_requires_first_core_module_operations_release() -> None:
    project = _project()["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    values = [str(item) for item in dependencies if str(item).startswith("pds-core")]
    assert values == ["pds-core>=0.6.2,<0.7"]
    requirement = Requirement(values[0])
    assert Version("0.6.2") in requirement.specifier
    assert Version("0.6.3") in requirement.specifier
    assert Version("0.6.1") not in requirement.specifier
    assert Version("0.7.0") not in requirement.specifier


def test_pyproject_declares_exact_operations_entry_point() -> None:
    project = _project()["project"]
    assert isinstance(project, dict)
    groups = project["entry-points"]
    assert isinstance(groups, dict)
    assert groups[MODULE_OPERATIONS_ENTRY_POINT_GROUP] == {
        "quillan": "quillan.pds_operations:get_module_operations_profile"
    }


def test_operations_provider_is_zero_argument_validated_attention_only_profile() -> None:
    assert tuple(inspect.signature(get_module_operations_profile).parameters) == ()
    profile = get_module_operations_profile()
    assert isinstance(profile, ModuleOperationsProfile)
    assert validate_module_operations_profile(profile) == profile
    assert profile.module_id == "quillan"
    assert profile.attention_provider is not None
    assert profile.readiness_provider is None


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


def test_exact_core_wheel_verifier_keeps_historical_and_current_contracts() -> None:
    from scripts.verify_core_wheel import CORE_WHEEL_CONTRACTS

    assert tuple(sorted(CORE_WHEEL_CONTRACTS)) == ("0.6.0", "0.6.2", "0.6.3")
    minimum = CORE_WHEEL_CONTRACTS["0.6.2"]
    assert minimum.filename == "pds_core-0.6.2-py3-none-any.whl"
    assert minimum.version == "0.6.2"
    assert (
        minimum.sha256
        == "b9d5de7d467d18716f415da87f359e940603d9c738a3a9ae9309272ebe78a848"
    )


def test_ci_uses_062_as_current_minimum_and_keeps_063_qualification() -> None:
    source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "Download released Core 0.6.2" in source
    assert source.count("pds_core-0.6.2-py3-none-any.whl") >= 4
    assert source.count("--core-version 0.6.2") >= 2
    assert (
        'verify_core_wheel.py "${{ runner.temp }}/pds_core-0.6.2-py3-none-any.whl" '
        "--core-version 0.6.2"
    ) in source
    assert (
        'verify_core_wheel.py "${{ runner.temp }}/pds_core-0.6.2-py3-none-any.whl" '
        "--core-version 0.6.2 --verify-installed"
    ) in source
    validation_prefix = source.split("core-063-qualification:", 1)[0]
    assert "pds_core-0.6.0-py3-none-any.whl" not in validation_prefix
    assert "--core-version 0.6.0" not in validation_prefix
    assert "Download released Core 0.6.0" not in source
    assert "core-063-qualification:" in source
    assert "Download released Core 0.6.3" in source
    assert "--core-version 0.6.3" in source


def test_historical_release_candidate_contract_remains_explicitly_060() -> None:
    source = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert source.count("'--core-version', '0.6.0'") == 2
    assert "'--expected-core-version', '0.6.0'" in source

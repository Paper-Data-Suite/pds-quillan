from __future__ import annotations

import os
from pathlib import Path
import tomllib

import pytest

from scripts.run_operations_wheel_acceptance import (
    OperationsWheelAcceptanceError,
    _environment_python,
)


ROOT = Path(__file__).resolve().parents[1]


def test_environment_python_is_platform_specific(tmp_path: Path) -> None:
    path = _environment_python(tmp_path)
    if os.name == "nt":
        assert path == tmp_path / "Scripts" / "python.exe"
    else:
        assert path == tmp_path / "bin" / "python"


def test_operations_wheel_harness_is_explicit_built_artifact_acceptance() -> None:
    source = (
        ROOT / "scripts" / "run_operations_wheel_acceptance.py"
    ).read_text(encoding="utf-8")
    assert '"build"' in source
    assert '"--wheel"' in source
    assert '"--sdist"' in source
    assert "inspect_release_artifacts.py" in source
    assert "run_installed_acceptance.py" in source
    assert '"--full-workflow"' in source
    assert "verify_installed_producer_acceptance.py" in source
    assert "verify_installed_operations_acceptance.py" in source
    assert 'choices=("0.6.2", "0.6.3")' in source
    assert '"-e"' not in source


def test_installed_application_acceptance_accepts_explicit_core_endpoint() -> None:
    source = (ROOT / "scripts" / "run_installed_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert '"--expected-core-version"' in source
    assert 'choices=("0.6.0", "0.6.2", "0.6.3")' in source
    assert 'default="0.6.0"' in source
    assert "core_distribution.version == args.expected_core_version" in source
    assert 'core_distribution.version == "0.6.0"' not in source

    harness = (
        ROOT / "scripts" / "run_operations_wheel_acceptance.py"
    ).read_text(encoding="utf-8")
    assert '"--expected-core-version"' in harness
    assert "expected_core_version" in harness


def test_installed_producer_acceptance_uses_requested_core_endpoint() -> None:
    source = (
        ROOT / "scripts" / "verify_installed_producer_acceptance.py"
    ).read_text(encoding="utf-8")
    assert "installed_core == core_version" in source
    assert 'installed_core == core_version == "0.6.0"' not in source
    assert (
        "Quillan dependency metadata rejects the selected Core version."
        in source
    )
    assert "Quillan dependency metadata rejects Core 0.6.0." not in source


def test_current_artifact_contract_requires_operations_provider_and_core062() -> None:
    source = (ROOT / "scripts" / "inspect_release_artifacts.py").read_text(
        encoding="utf-8"
    )
    assert '"quillan/pds_operations.py"' in source
    assert '"quillan/attention_provider.py"' in source
    assert '"paper_data_suite.module_operations"' in source
    assert '">=0.6.2"' in source


def test_ci_runs_built_wheel_acceptance_for_minimum_and_current_core() -> None:
    source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "operations-wheel-qualification:" in source
    assert 'core: "0.6.2"' in source
    assert 'core: "0.6.3"' in source
    assert "run_operations_wheel_acceptance.py" in source
    assert "--expected-core-version" in source
    assert "windows-latest" in source
    assert "ubuntu-latest" in source


def test_active_dependency_contract_matches_artifact_acceptance_floor() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pds-core>=0.6.2,<0.7" in project["project"]["dependencies"]


def test_harness_refuses_nonempty_work_directory(tmp_path: Path) -> None:
    from scripts.run_operations_wheel_acceptance import run_acceptance

    work = tmp_path / "work"
    work.mkdir()
    (work / "sentinel").write_text("keep", encoding="utf-8")
    core = tmp_path / "core.whl"
    core.write_bytes(b"synthetic")
    repository = tmp_path / "repo"
    repository.mkdir()

    with pytest.raises(
        OperationsWheelAcceptanceError,
        match="absent or an empty",
    ):
        run_acceptance(
            repository=repository,
            work=work,
            core_wheel=core,
            expected_core_version="0.6.2",
        )
    assert (work / "sentinel").read_text(encoding="utf-8") == "keep"

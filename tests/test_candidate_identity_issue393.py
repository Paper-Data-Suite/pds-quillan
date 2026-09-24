from __future__ import annotations

from pathlib import Path
import tomllib

import quillan
from quillan._version import __version__
from scripts.inspect_release_artifacts import EXPECTED_VERSION
from scripts.persist_release_artifacts import ARTIFACT_NAMES

ROOT = Path(__file__).resolve().parents[1]


def test_patch_candidate_identity_is_exact_v0102() -> None:
    assert quillan.__version__ == __version__ == "0.10.2"
    assert EXPECTED_VERSION == "0.10.2"
    assert ARTIFACT_NAMES == (
        "quillan-0.10.2-py3-none-any.whl",
        "quillan-0.10.2.tar.gz",
    )


def test_issue393_core_runtime_range_is_unchanged() -> None:
    with (ROOT / "pyproject.toml").open("rb") as source:
        project = tomllib.load(source)["project"]
    core = [
        dependency
        for dependency in project["dependencies"]
        if dependency.startswith("pds-core")
    ]
    assert core == ["pds-core>=0.6.2,<0.7"]


def test_issue393_installed_acceptance_targets_candidate_identity() -> None:
    source = (ROOT / "scripts" / "run_installed_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert 'EXPECTED_VERSION = "0.10.2"' in source
    assert 'EXPECTED_VERSION = "0.9.0"' not in source


def test_issue393_preserves_v090_historical_release_evidence() -> None:
    required = (
        ROOT / "docs" / "releases" / "v0.9.0.md",
        ROOT / "docs" / "releases" / "v0.9.0_acceptance_matrix.md",
        ROOT / "docs" / "physical_acceptance_v0.9.0.md",
    )
    for path in required:
        assert path.is_file()
        assert "0.9.0" in path.read_text(encoding="utf-8")


def test_issue393_installed_cli_version_probe_uses_candidate_constant() -> None:
    source = (ROOT / "scripts" / "run_installed_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert 'f"quillan {EXPECTED_VERSION}\\n"' in source
    assert '"quillan 0.9.0\\n"' not in source

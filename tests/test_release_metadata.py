"""Single-source release metadata contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

import quillan
from quillan._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_has_one_runtime_source() -> None:
    with (ROOT / "pyproject.toml").open("rb") as source:
        configuration = tomllib.load(source)
    project = configuration["project"]
    assert "version" not in project
    assert project["dynamic"] == ["version"]
    assert configuration["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "quillan._version.__version__"
    }
    assert quillan.__version__ == __version__ == "0.10.1"


def test_release_license_and_python_metadata_are_current() -> None:
    with (ROOT / "pyproject.toml").open("rb") as source:
        project = tomllib.load(source)["project"]
    assert project["requires-python"] == ">=3.11"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert (ROOT / "LICENSE").is_file()


def test_active_release_documents_name_the_candidate_version() -> None:
    for relative in (
        "README.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "docs/release_process.md",
        "docs/release_checklist.md",
        "docs/v0.10.1_installed_batch_feedback_acceptance.md",
    ):
        assert "0.10.1" in (ROOT / relative).read_text(encoding="utf-8"), relative


def test_prior_release_evidence_remains_historical() -> None:
    for relative in (
        "docs/v0.10.0_installed_class_set_acceptance.md",
        "docs/physical_acceptance_v0.10.0.md",
    ):
        assert "0.10.0" in (ROOT / relative).read_text(encoding="utf-8"), relative

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
    assert quillan.__version__ == __version__ == "0.8.9"


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
        "docs/releases/v0.8.9.md",
        "docs/release_checklist.md",
    ):
        assert "0.8.9" in (ROOT / relative).read_text(encoding="utf-8"), relative

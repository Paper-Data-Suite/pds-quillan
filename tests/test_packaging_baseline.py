"""Regression tests for Quillan's installed-package baseline."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

REPOSITORY = Path(__file__).resolve().parents[1]


def _configuration() -> dict[str, object]:
    with (REPOSITORY / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)


def test_runtime_declares_one_ordinary_core_requirement() -> None:
    project = _configuration()["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)

    core_values = [
        value
        for value in dependencies
        if Requirement(value).name == "pds-core"
    ]
    assert core_values == ["pds-core>=0.5,<0.6"]

    requirement = Requirement(core_values[0])
    assert requirement.name.lower().replace("_", "-") == "pds-core"
    assert requirement.url is None
    assert {str(value) for value in requirement.specifier} == {">=0.5", "<0.6"}
    assert "@" not in core_values[0]
    assert not any(
        marker in core_values[0].lower()
        for marker in ("file:", "git+", "hg+", "svn+", "bzr+", "../", "..\\")
    )


def test_development_extras_declare_packaging_directly() -> None:
    project = _configuration()["project"]
    assert isinstance(project, dict)
    optional_dependencies = project["optional-dependencies"]
    assert isinstance(optional_dependencies, dict)
    dev_dependencies = optional_dependencies["dev"]
    assert isinstance(dev_dependencies, list)

    names = {Requirement(value).name for value in dev_dependencies}
    assert "packaging" in names


def test_setuptools_build_and_complete_namespace_discovery_are_explicit() -> None:
    configuration = _configuration()
    assert configuration["build-system"] == {
        "requires": ["setuptools>=61"],
        "build-backend": "setuptools.build_meta",
    }

    tool = configuration["tool"]
    assert isinstance(tool, dict)
    discovery = tool["setuptools"]["packages"]["find"]
    assert discovery == {
        "where": ["."],
        "include": ["quillan*"],
        "namespaces": True,
    }


def test_mypy_does_not_use_core_source_paths_or_global_import_suppression() -> None:
    tool = _configuration()["tool"]
    assert isinstance(tool, dict)
    mypy = tool["mypy"]
    assert "mypy_path" not in mypy
    assert mypy.get("ignore_missing_imports") is not True


def test_requirements_dev_installs_only_local_quillan_extras() -> None:
    content = (REPOSITORY / "requirements-dev.txt").read_text(encoding="utf-8")
    assert content == (
        "# Development dependencies are authoritative in pyproject.toml.\n"
        "-e .[dev]\n"
    )
    assert "../pds-core" not in content

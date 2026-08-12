"""Focused release-archive path enforcement tests."""

from __future__ import annotations

from pathlib import Path
import tarfile
import zipfile

import pytest

from scripts.inspect_release_artifacts import inspect_sdist, inspect_wheel


REMOVED_MODULES = (
    "quillan/submissions.py",
    "quillan/evidence_filing.py",
    "quillan/routing_review.py",
    "quillan/storage.py",
)


def _metadata(*requirements: str) -> str:
    requires_dist = "".join(
        f"Requires-Dist: {requirement}\n" for requirement in requirements
    )
    return f"""Metadata-Version: 2.4
Name: quillan
Version: 0.8.9
Requires-Python: >=3.11
{requires_dist}\
License-Expression: MIT
License-File: LICENSE
"""


VALID_METADATA = _metadata("pds-core<0.7,>=0.6")


def _wheel(
    path: Path,
    extra_name: str = "quillan/current.py",
    *,
    metadata: str = VALID_METADATA,
) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("quillan/_version.py", '__version__ = "0.8.9"\n')
        archive.writestr(extra_name, "")
        archive.writestr("quillan-0.8.9.dist-info/METADATA", metadata)
        archive.writestr(
            "quillan-0.8.9.dist-info/entry_points.txt",
            "[console_scripts]\nquillan = quillan.cli:main\n"
            "[paper_data_suite.modules]\n"
            "quillan = quillan.pds_module:get_module_profile\n",
        )
        archive.writestr("quillan-0.8.9.dist-info/licenses/LICENSE", "MIT\n")
    return path


def _sdist(
    path: Path,
    extra_name: str = "quillan/current.py",
    *,
    metadata: str = VALID_METADATA,
) -> Path:
    root = path.parent / f"{path.name}.source"
    package = root / "quillan-0.8.9"
    (package / "quillan").mkdir(parents=True)
    (package / "PKG-INFO").write_text(metadata, encoding="utf-8")
    (package / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (package / "README.md").write_text("Quillan\n", encoding="utf-8")
    (package / "quillan" / "_version.py").write_text(
        '__version__ = "0.8.9"\n', encoding="utf-8"
    )
    target = package.joinpath(*extra_name.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    with tarfile.open(path, "w:gz") as archive:
        archive.add(package, arcname=package.name)
    return path


@pytest.mark.parametrize("removed", REMOVED_MODULES)
def test_wheel_rejects_each_removed_module(tmp_path: Path, removed: str) -> None:
    artifact = _wheel(tmp_path / "synthetic.whl", removed)
    with pytest.raises(AssertionError):
        inspect_wheel(artifact)


@pytest.mark.parametrize("removed", REMOVED_MODULES)
def test_sdist_rejects_each_removed_module(tmp_path: Path, removed: str) -> None:
    artifact = _sdist(tmp_path / "synthetic.tar.gz", removed)
    with pytest.raises(AssertionError):
        inspect_sdist(artifact)


def test_ordinary_current_package_paths_are_accepted(tmp_path: Path) -> None:
    assert inspect_wheel(_wheel(tmp_path / "current.whl"))["version"] == "0.8.9"
    assert inspect_sdist(_sdist(tmp_path / "current.tar.gz"))["version"] == "0.8.9"


def test_wheel_rejects_bundled_core_source(tmp_path: Path) -> None:
    artifact = _wheel(tmp_path / "bundled-core.whl", "pds_core/routing_models.py")
    with pytest.raises(AssertionError):
        inspect_wheel(artifact)


def test_sdist_rejects_bundled_core_source(tmp_path: Path) -> None:
    artifact = _sdist(tmp_path / "bundled-core.tar.gz", "pds_core/routing_models.py")
    with pytest.raises(AssertionError):
        inspect_sdist(artifact)


INVALID_CORE_REQUIREMENTS = (
    pytest.param((), id="missing"),
    pytest.param(
        ("pds-core>=0.6,<0.7", "pds-core>=0.6,<0.7"),
        id="duplicate-canonical",
    ),
    pytest.param(
        ("pds-core>=0.6,<0.7", "pds_core>=0.6,<0.7"),
        id="duplicate-underscore-alias",
    ),
    pytest.param(
        ("pds-core>=0.6,<0.7", "PDS.Core>=0.6,<0.7"),
        id="duplicate-dot-case-alias",
    ),
    pytest.param(("pds-core>=0.5,<0.6",), id="old-range"),
    pytest.param(("pds-core>=0.7,<0.8",), id="core-07-only"),
    pytest.param(("pds-core>=0.6",), id="unbounded"),
    pytest.param(
        ("pds-core @ https://example.invalid/pds_core.whl",),
        id="direct-url",
    ),
    pytest.param(("pds-core[test]>=0.6,<0.7",), id="extra"),
    pytest.param(
        ('pds-core>=0.6,<0.7; python_version >= "3.11"',),
        id="environment-marker",
    ),
)


@pytest.mark.parametrize("requirements", INVALID_CORE_REQUIREMENTS)
@pytest.mark.parametrize("artifact_kind", ("wheel", "sdist"))
def test_artifacts_reject_invalid_core_dependency_contracts(
    tmp_path: Path,
    artifact_kind: str,
    requirements: tuple[str, ...],
) -> None:
    metadata = _metadata(*requirements)
    if artifact_kind == "wheel":
        artifact = _wheel(tmp_path / "invalid.whl", metadata=metadata)
        inspect = inspect_wheel
    else:
        artifact = _sdist(tmp_path / "invalid.tar.gz", metadata=metadata)
        inspect = inspect_sdist
    with pytest.raises(AssertionError):
        inspect(artifact)

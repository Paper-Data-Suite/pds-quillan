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


METADATA = """Metadata-Version: 2.4
Name: quillan
Version: 0.8.9
Requires-Python: >=3.11
Requires-Dist: pds-core<0.6,>=0.5
License-Expression: MIT
License-File: LICENSE
"""


def _wheel(path: Path, extra_name: str = "quillan/current.py") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("quillan/_version.py", '__version__ = "0.8.9"\n')
        archive.writestr(extra_name, "")
        archive.writestr("quillan-0.8.9.dist-info/METADATA", METADATA)
        archive.writestr(
            "quillan-0.8.9.dist-info/entry_points.txt",
            "[console_scripts]\nquillan = quillan.cli:main\n"
            "[paper_data_suite.modules]\n"
            "quillan = quillan.pds_module:get_module_profile\n",
        )
        archive.writestr("quillan-0.8.9.dist-info/licenses/LICENSE", "MIT\n")
    return path


def _sdist(path: Path, extra_name: str = "quillan/current.py") -> Path:
    root = path.parent / "source"
    package = root / "quillan-0.8.9"
    (package / "quillan").mkdir(parents=True)
    (package / "PKG-INFO").write_text(METADATA, encoding="utf-8")
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

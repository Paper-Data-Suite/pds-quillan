"""Focused release-archive path enforcement tests."""

from __future__ import annotations

from pathlib import Path
import tarfile
import zipfile

import pytest

from scripts.inspect_release_artifacts import (
    inspect_sdist,
    inspect_wheel,
    validate_entry_points_text,
)


REMOVED_MODULES = (
    "quillan/submissions.py",
    "quillan/evidence_filing.py",
    "quillan/routing_review.py",
    "quillan/storage.py",
)
FORBIDDEN_SIBLING_ROOTS = (
    "meridian",
    "pds_meridian",
    "vitrine",
    "pds_vitrine",
    "scoreform",
    "pds_scoreform",
    "concord",
    "pds_concord",
    "portia",
    "pds_portia",
)


def _metadata(*requirements: str) -> str:
    requires_dist = "".join(
        f"Requires-Dist: {requirement}\n" for requirement in requirements
    )
    return f"""Metadata-Version: 2.4
Name: quillan
Version: 0.9.0
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
        for required in (
            "pds_module.py",
            "pds_publication.py",
            "academic_work_registration.py",
            "academic_result_manifest.py",
            "academic_result_manifest_generation.py",
            "academic_result_publication.py",
            "academic_result_reader.py",
            "academic_result_artifacts.py",
        ):
            archive.writestr(f"quillan/{required}", "")
        archive.writestr("quillan/_version.py", '__version__ = "0.9.0"\n')
        archive.writestr(extra_name, "")
        archive.writestr("quillan-0.9.0.dist-info/METADATA", metadata)
        archive.writestr(
            "quillan-0.9.0.dist-info/entry_points.txt",
            "[console_scripts]\nquillan = quillan.cli:main\n"
            "[paper_data_suite.modules]\n"
            "quillan = quillan.pds_module:get_module_profile\n"
            "[paper_data_suite.publication_producers]\n"
            "quillan = quillan.pds_publication:get_publication_producer_profile\n",
        )
        archive.writestr("quillan-0.9.0.dist-info/licenses/LICENSE", "MIT\n")
    return path


def _sdist(
    path: Path,
    extra_name: str = "quillan/current.py",
    *,
    metadata: str = VALID_METADATA,
    package_name: str = "quillan-0.9.0",
) -> Path:
    root = path.parent / f"{path.name}.source"
    package = root / package_name
    (package / "quillan").mkdir(parents=True)
    (package / "PKG-INFO").write_text(metadata, encoding="utf-8")
    (package / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (package / "README.md").write_text("Quillan\n", encoding="utf-8")
    (package / "quillan" / "_version.py").write_text(
        '__version__ = "0.9.0"\n', encoding="utf-8"
    )
    for required in (
        "pds_module.py",
        "pds_publication.py",
        "academic_work_registration.py",
        "academic_result_manifest.py",
        "academic_result_manifest_generation.py",
        "academic_result_publication.py",
        "academic_result_reader.py",
        "academic_result_artifacts.py",
    ):
        (package / "quillan" / required).write_text("", encoding="utf-8")
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
    assert inspect_wheel(_wheel(tmp_path / "current.whl"))["version"] == "0.9.0"
    assert inspect_sdist(_sdist(tmp_path / "current.tar.gz"))["version"] == "0.9.0"


@pytest.mark.parametrize(
    "text",
    (
        "[paper_data_suite.modules]\nquillan = quillan.pds_module:get_module_profile\n",
        """[paper_data_suite.modules]
quillan = quillan.pds_module:get_module_profile
[paper_data_suite.publication_producers]
other = quillan.pds_publication:get_publication_producer_profile
""",
        """[paper_data_suite.modules]
quillan = quillan.pds_module:get_module_profile
[paper_data_suite.publication_producers]
quillan = quillan.pds_publication:wrong
""",
        """[paper_data_suite.modules]
quillan = quillan.pds_publication:get_publication_producer_profile
[paper_data_suite.publication_producers]
quillan = quillan.pds_module:get_module_profile
""",
        """[paper_data_suite.modules]
quillan = quillan.pds_module:get_module_profile
[paper_data_suite.publication_producers]
quillan = quillan.pds_publication:get_publication_producer_profile
alias = quillan.pds_publication:get_publication_producer_profile
""",
    ),
)
def test_entry_point_contract_rejects_missing_wrong_swapped_or_alias_entries(
    text: str,
) -> None:
    with pytest.raises(AssertionError):
        validate_entry_points_text(text)


def test_wheel_rejects_bundled_core_source(tmp_path: Path) -> None:
    artifact = _wheel(tmp_path / "bundled-core.whl", "pds_core/routing_models.py")
    with pytest.raises(AssertionError):
        inspect_wheel(artifact)


def test_sdist_rejects_bundled_core_source(tmp_path: Path) -> None:
    artifact = _sdist(tmp_path / "bundled-core.tar.gz", "pds_core/routing_models.py")
    with pytest.raises(AssertionError):
        inspect_sdist(artifact)


@pytest.mark.parametrize("package_root", FORBIDDEN_SIBLING_ROOTS)
@pytest.mark.parametrize("artifact_kind", ("wheel", "sdist"))
def test_artifacts_reject_bundled_sibling_source(
    tmp_path: Path,
    artifact_kind: str,
    package_root: str,
) -> None:
    extra = f"{package_root}/consumer_policy.py"
    if artifact_kind == "wheel":
        artifact = _wheel(tmp_path / "bundled-sibling.whl", extra)
        inspect = inspect_wheel
    else:
        artifact = _sdist(tmp_path / "bundled-sibling.tar.gz", extra)
        inspect = inspect_sdist
    with pytest.raises(AssertionError):
        inspect(artifact)


def test_sdist_requires_exact_release_root(tmp_path: Path) -> None:
    artifact = _sdist(
        tmp_path / "wrong-root.tar.gz",
        package_name="not-quillan-0.9.0",
    )
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

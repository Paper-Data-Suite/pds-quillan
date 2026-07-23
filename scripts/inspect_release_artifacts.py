"""Inspect Quillan wheel and sdist release contracts without extracting them."""

from __future__ import annotations

import argparse
from email.parser import Parser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

EXPECTED_VERSION = "0.8.9"
REMOVED = {
    "quillan/submissions.py",
    "quillan/evidence_filing.py",
    "quillan/routing_review.py",
    "quillan/storage.py",
}
FORBIDDEN_PARTS = {
    ".git", ".venv", ".pytest-tmp", "build", "dist", "__pycache__",
    ".mypy_cache", ".ruff_cache",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_names(names: set[str]) -> None:
    normalized_names: set[str] = set()
    for name in names:
        normalized = PurePosixPath(name)
        assert not (set(normalized.parts) & FORBIDDEN_PARTS), name
        assert not re.match(r"^[A-Za-z]:[/\\]", name), name
        parts = normalized.parts
        if parts and parts[0] == f"quillan-{EXPECTED_VERSION}":
            parts = parts[1:]
        normalized_names.add(PurePosixPath(*parts).as_posix())
    assert not (REMOVED & normalized_names), names


def _metadata_contract(raw: str) -> dict[str, object]:
    metadata = Parser().parsestr(raw)
    requirements = metadata.get_all("Requires-Dist", [])
    assert metadata["Name"] == "quillan", metadata["Name"]
    assert metadata["Version"] == EXPECTED_VERSION, metadata["Version"]
    assert metadata["Requires-Python"] == ">=3.11", metadata["Requires-Python"]
    assert metadata["License-Expression"] == "MIT", metadata.items()
    assert "License-File" in metadata and "LICENSE" in metadata["License-File"]
    assert any(value.startswith("pds-core<0.6,>=0.5") for value in requirements)
    return {
        "version": metadata["Version"],
        "requires_python": metadata["Requires-Python"],
        "core_requirement": next(v for v in requirements if v.startswith("pds-core")),
        "license": metadata["License-Expression"],
    }


def inspect_wheel(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        _validate_names(names)
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        entry_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        metadata = _metadata_contract(archive.read(metadata_name).decode("utf-8"))
        entries = archive.read(entry_name).decode("utf-8")
        assert "quillan = quillan.cli:main" in entries
        assert "quillan = quillan.pds_module:get_module_profile" in entries
        assert "quillan/_version.py" in names
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    return {"filename": path.name, "sha256": _sha256(path), **metadata}


def inspect_sdist(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r:gz") as archive:
        names = {member.name for member in archive.getmembers()}
        _validate_names(names)
        pkg_info = next(member for member in archive.getmembers() if member.name.endswith("/PKG-INFO"))
        source = archive.extractfile(pkg_info)
        assert source is not None
        metadata = _metadata_contract(source.read().decode("utf-8"))
        assert any(name.endswith("/LICENSE") for name in names)
        assert any(name.endswith("/README.md") for name in names)
        assert any(name.endswith("/quillan/_version.py") for name in names)
    return {"filename": path.name, "sha256": _sha256(path), **metadata}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("sdist", type=Path)
    args = parser.parse_args()
    assert args.wheel.name == f"quillan-{EXPECTED_VERSION}-py3-none-any.whl"
    assert args.sdist.name == f"quillan-{EXPECTED_VERSION}.tar.gz"
    print(json.dumps({"wheel": inspect_wheel(args.wheel), "sdist": inspect_sdist(args.sdist)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

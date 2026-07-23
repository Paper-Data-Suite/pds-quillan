"""Persist the exact release artifacts exercised by the candidate validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Final


ARTIFACT_NAMES: Final = (
    "quillan-0.8.9-py3-none-any.whl",
    "quillan-0.8.9.tar.gz",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    return path.is_symlink() or bool(is_junction(path))


def persist_tested_artifacts(
    repository: Path,
    output_directory: Path,
    wheel: Path,
    sdist: Path,
) -> dict[str, dict[str, str]]:
    """Copy tested artifacts once and prove source/destination byte identity."""
    repository = repository.resolve(strict=True)
    sources = (wheel.resolve(strict=True), sdist.resolve(strict=True))
    if tuple(path.name for path in sources) != ARTIFACT_NAMES:
        raise ValueError("Unexpected release artifact filename.")
    if not all(path.is_file() for path in sources):
        raise ValueError("Tested release artifacts must be ordinary files.")

    requested_output = output_directory.absolute()
    if requested_output.exists():
        if not requested_output.is_dir() or _is_link_or_junction(requested_output):
            raise ValueError("Artifact output directory must be an ordinary directory.")
        if any(requested_output.iterdir()):
            raise ValueError("Artifact output directory must be empty.")
    else:
        parent = requested_output.parent.resolve(strict=True)
        if not parent.is_dir() or _is_link_or_junction(parent):
            raise ValueError("Artifact output parent must be an ordinary directory.")
        candidate = parent / requested_output.name
        if candidate == repository or candidate.is_relative_to(repository):
            raise ValueError(
                "Artifact output directory must resolve outside the repository."
            )
        requested_output.mkdir()

    if _is_link_or_junction(requested_output):
        raise ValueError("Artifact output directory must not be a symlink or junction.")
    output = requested_output.resolve(strict=True)
    if output == repository or output.is_relative_to(repository):
        raise ValueError("Artifact output directory must resolve outside the repository.")

    result: dict[str, dict[str, str]] = {}
    for source in sources:
        destination = output / source.name
        if destination.exists():
            raise ValueError(f"Refusing to overwrite artifact: {destination}")
        source_hash = _sha256(source)
        shutil.copyfile(source, destination)
        destination_hash = _sha256(destination)
        if destination_hash != source_hash:
            raise ValueError(f"Persisted artifact hash mismatch: {source.name}")
        result[source.name] = {
            "tested_path": str(source),
            "tested_sha256": source_hash,
            "persistent_path": str(destination.resolve()),
            "persistent_sha256": destination_hash,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    args = parser.parse_args()
    result = persist_tested_artifacts(
        args.repository,
        args.output_directory,
        args.wheel,
        args.sdist,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

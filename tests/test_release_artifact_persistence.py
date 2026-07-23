"""Focused exact-tested-artifact persistence tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from typing import Any

import pytest

from scripts.persist_release_artifacts import persist_tested_artifacts


def _fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    repository = root / "repository"
    tested = root / "validator-temporary-artifacts"
    output = root / "persistent-candidate"
    repository.mkdir()
    tested.mkdir()
    wheel = tested / "quillan-0.8.9-py3-none-any.whl"
    sdist = tested / "quillan-0.8.9.tar.gz"
    wheel.write_bytes(b"synthetic tested wheel bytes")
    sdist.write_bytes(b"synthetic tested sdist bytes")
    return repository, output, wheel, sdist


def test_persisted_artifacts_are_exact_tested_bytes(tmp_path: Path) -> None:
    repository, output, wheel, sdist = _fixture(tmp_path)
    result = persist_tested_artifacts(repository, output, wheel, sdist)
    for source in (wheel, sdist):
        record = result[source.name]
        copied = output / source.name
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        assert copied.read_bytes() == source.read_bytes()
        assert record["tested_sha256"] == record["persistent_sha256"] == expected
        assert Path(record["persistent_path"]) == copied.resolve()


def test_persistence_rejects_post_copy_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, output, wheel, sdist = _fixture(tmp_path)
    original = shutil.copyfile

    def corrupt_copy(source: Path, destination: Path) -> Any:
        result = original(source, destination)
        Path(destination).write_bytes(Path(destination).read_bytes() + b"corrupt")
        return result

    monkeypatch.setattr(shutil, "copyfile", corrupt_copy)
    with pytest.raises(ValueError, match="hash mismatch"):
        persist_tested_artifacts(repository, output, wheel, sdist)


def test_persistence_rejects_repository_output_and_nonempty_output(
    tmp_path: Path,
) -> None:
    repository, output, wheel, sdist = _fixture(tmp_path)
    with pytest.raises(ValueError, match="outside the repository"):
        persist_tested_artifacts(repository, repository / "artifacts", wheel, sdist)
    output.mkdir()
    (output / "existing.txt").write_text("occupied", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        persist_tested_artifacts(repository, output, wheel, sdist)

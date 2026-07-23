"""UTF-8 and byte-identity tests for #343 review artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from scripts.generate_review_artifacts import (
    _file_block,
    embedded_files,
    generate_full_changes,
    verify_embedded_untracked_files,
)


MOJIBAKE = ("\ufffd", "\u00c3", "\u00e2\u20ac", "\u00c2\u00a0")


def test_exact_utf8_block_round_trips_bytes_and_hash() -> None:
    content = "Actual em dash — and final newline.\n".encode()
    block = embedded_files(_file_block("docs/example.md", content))[0]
    assert block.content == content
    assert block.sha256 == hashlib.sha256(content).hexdigest()


def test_generated_full_changes_is_strict_utf8_and_matches_untracked_files(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "quillan-tests@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Quillan Tests"],
        cwd=repository,
        check=True,
    )
    tracked = repository / "tracked.txt"
    tracked.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repository, check=True)
    tracked.write_text("Changed with an em dash —.\n", encoding="utf-8")
    (repository / "untracked.txt").write_text(
        "Exact untracked UTF-8 — bytes.\n", encoding="utf-8"
    )
    artifact = tmp_path / "full-changes.txt"
    count = generate_full_changes(repository, artifact)
    text = artifact.read_text(encoding="utf-8", errors="strict")
    assert count == 1
    assert verify_embedded_untracked_files(repository, artifact) == count
    assert not any(sequence in text for sequence in MOJIBAKE)

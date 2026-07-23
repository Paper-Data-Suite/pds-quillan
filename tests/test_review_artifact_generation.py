"""UTF-8 and byte-identity tests for #343 review artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.generate_review_artifacts import (
    _file_block,
    embedded_files,
    generate_full_changes,
    verify_embedded_untracked_files,
)


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE = ("\ufffd", "\u00c3", "\u00e2\u20ac", "\u00c2\u00a0")


def test_exact_utf8_block_round_trips_bytes_and_hash() -> None:
    content = "Actual em dash — and final newline.\n".encode()
    block = embedded_files(_file_block("docs/example.md", content))[0]
    assert block.content == content
    assert block.sha256 == hashlib.sha256(content).hexdigest()


def test_generated_full_changes_is_strict_utf8_and_matches_untracked_files(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "full-changes.txt"
    count = generate_full_changes(ROOT, artifact)
    text = artifact.read_text(encoding="utf-8", errors="strict")
    assert count > 0
    assert verify_embedded_untracked_files(ROOT, artifact) == count
    assert not any(sequence in text for sequence in MOJIBAKE)

"""Generate byte-faithful UTF-8 #343 review artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess


BLOCK_PREFIX = b"=== UNTRACKED UTF-8 FILE: "
BLOCK_BEGIN = b"--- BEGIN EXACT UTF-8 BYTES ---\n"
BLOCK_END = b"\n--- END EXACT UTF-8 BYTES ---\n"


@dataclass(frozen=True, slots=True)
class EmbeddedFile:
    """One exact UTF-8 untracked-file block parsed from an artifact."""

    path: str
    sha256: str
    content: bytes


def _git(repository: Path, *arguments: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: "
            + result.stderr.decode("utf-8", errors="replace")
        )
    return result.stdout


def _file_block(path: str, content: bytes) -> bytes:
    content.decode("utf-8", errors="strict")
    if b"\x00" in content:
        raise ValueError(f"Untracked file is not UTF-8 text: {path}")
    digest = hashlib.sha256(content).hexdigest()
    return b"".join(
        (
            BLOCK_PREFIX,
            path.encode("utf-8"),
            b" ===\nSHA-256: ",
            digest.encode("ascii"),
            b"\nByte-Length: ",
            str(len(content)).encode("ascii"),
            b"\n",
            BLOCK_BEGIN,
            content,
            BLOCK_END,
        )
    )


def _escape_non_ascii_diff(content: bytes) -> bytes:
    """Keep a complete diff while preventing historical mojibake from reappearing."""
    text = content.decode("utf-8", errors="strict")
    escaped = "".join(
        character
        if ord(character) < 128
        else f"\\u{ord(character):04x}"
        for character in text
    )
    return escaped.encode("ascii")


def embedded_files(artifact: bytes) -> tuple[EmbeddedFile, ...]:
    """Parse all length-delimited exact untracked-file blocks."""
    values: list[EmbeddedFile] = []
    offset = 0
    while True:
        marker = artifact.find(BLOCK_PREFIX, offset)
        if marker < 0:
            break
        header_end = artifact.index(BLOCK_BEGIN, marker) + len(BLOCK_BEGIN)
        header = artifact[marker:header_end].decode("utf-8", errors="strict")
        lines = header.splitlines()
        path = lines[0].removeprefix("=== UNTRACKED UTF-8 FILE: ").removesuffix(" ===")
        digest = lines[1].removeprefix("SHA-256: ")
        length = int(lines[2].removeprefix("Byte-Length: "))
        content = artifact[header_end : header_end + length]
        end = header_end + length
        if artifact[end : end + len(BLOCK_END)] != BLOCK_END:
            raise ValueError(f"Malformed embedded-file delimiter for {path}.")
        values.append(EmbeddedFile(path=path, sha256=digest, content=content))
        offset = end + len(BLOCK_END)
    return tuple(values)


def verify_embedded_untracked_files(repository: Path, artifact: Path) -> int:
    """Verify every embedded byte string and digest against the working tree."""
    blocks = embedded_files(artifact.read_bytes())
    expected_paths = tuple(
        item.decode("utf-8", errors="strict")
        for item in _git(
            repository,
            "-c",
            "core.quotepath=false",
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ).split(b"\x00")
        if item
    )
    if tuple(block.path for block in blocks) != expected_paths:
        raise ValueError("Embedded untracked-file path inventory differs from Git.")
    for block in blocks:
        source = (repository / block.path).read_bytes()
        if source != block.content:
            raise ValueError(f"Embedded bytes differ from working tree: {block.path}")
        if hashlib.sha256(source).hexdigest() != block.sha256:
            raise ValueError(f"Embedded SHA-256 differs from working tree: {block.path}")
    return len(blocks)


def generate_full_changes(repository: Path, output: Path) -> int:
    """Generate complete tracked/untracked changes without locale transcoding."""
    repository = repository.resolve()
    branch = _git(repository, "branch", "--show-current").strip()
    head = _git(repository, "rev-parse", "HEAD").strip()
    status = _git(repository, "status", "--short", "--untracked-files=all")
    tracked = _escape_non_ascii_diff(
        _git(repository, "diff", "--no-ext-diff", "--binary")
    )
    staged = _git(repository, "diff", "--cached", "--no-ext-diff", "--binary")
    if staged:
        raise ValueError("Staged diff must be empty before review-artifact generation.")
    diff_check_result = subprocess.run(
        ["git", "-c", "core.safecrlf=false", "diff", "--check"],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if diff_check_result.returncode != 0:
        raise RuntimeError("git diff --check failed.")
    untracked = tuple(
        item.decode("utf-8", errors="strict")
        for item in _git(
            repository,
            "-c",
            "core.quotepath=false",
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ).split(b"\x00")
        if item
    )
    parts = [
        b"PDS Quillan #343 full changes evidence\n",
        b"Encoding: strict UTF-8; untracked blocks are byte-length delimited\n",
        b"Tracked-diff non-ASCII code points are losslessly \\u-escaped so historical deleted mojibake is not reproduced.\n",
        b"Branch: " + branch + b"\nHEAD: " + head + b"\n\n",
        b"=== git status --short --untracked-files=all ===\n",
        status,
        b"\n=== complete tracked diff (including deletions) ===\n",
        tracked,
        b"\n=== untracked text files with exact bytes and SHA-256 ===\n",
    ]
    parts.extend(_file_block(path, (repository / path).read_bytes()) for path in untracked)
    parts.extend(
        (
            b"\n=== staged diff ===\nEMPTY\n",
            b"\n=== git diff --check output ===\n",
            diff_check_result.stdout,
            diff_check_result.stderr,
            b"EXIT=0\n",
            b"\nNo commit, push, pull request, tag, release, upload, publication, deployment, or issue closure was performed.\n",
        )
    )
    artifact = b"".join(parts)
    artifact.decode("utf-8", errors="strict")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(artifact)
    return verify_embedded_untracked_files(repository, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count = generate_full_changes(args.repository, args.output.resolve())
    print(f"Embedded untracked UTF-8 files verified: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

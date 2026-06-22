"""Tests for safe local evidence opening."""

from __future__ import annotations

from pathlib import Path

from pds_core.local_open import LocalOpenError
import pytest

import quillan.evidence_opening as evidence_opening
from quillan.evidence_opening import (
    EvidenceOpeningError,
    OpenedEvidence,
    open_workspace_evidence,
    resolve_workspace_evidence_path,
)


def test_resolves_workspace_relative_evidence_path(tmp_path: Path) -> None:
    relative_path = Path("classes") / "english12_p3" / "scan.pdf"

    resolved = resolve_workspace_evidence_path(tmp_path, relative_path)

    assert resolved == (tmp_path / relative_path).resolve(strict=False)


@pytest.mark.parametrize(
    "evidence_path",
    [
        "",
        "   ",
        "http://example.com/evidence.pdf",
        "HTTPS://example.com/evidence.pdf",
        "file:///tmp/evidence.pdf",
        r"C:\outside\evidence.pdf",
    ],
)
def test_rejects_non_relative_local_paths(
    tmp_path: Path,
    evidence_path: str,
) -> None:
    with pytest.raises(EvidenceOpeningError):
        resolve_workspace_evidence_path(tmp_path, evidence_path)


def test_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(EvidenceOpeningError, match="relative"):
        resolve_workspace_evidence_path(tmp_path, tmp_path / "evidence.pdf")


def test_rejects_path_traversal_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    with pytest.raises(EvidenceOpeningError, match="inside"):
        resolve_workspace_evidence_path(workspace, "../outside.pdf")


def test_opens_existing_file_and_returns_workspace_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_path = tmp_path / "classes" / "class_1" / "scan.pdf"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"synthetic evidence")
    before_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    before_contents = evidence_path.read_bytes()
    opened_paths: list[Path] = []

    def fake_open_local_path(path: str | Path) -> Path:
        opened_path = Path(path)
        opened_paths.append(opened_path)
        return opened_path

    monkeypatch.setattr(
        evidence_opening,
        "open_local_path",
        fake_open_local_path,
    )

    result = open_workspace_evidence(
        tmp_path,
        "classes/class_1/scan.pdf",
    )

    assert result == OpenedEvidence(
        evidence_path=evidence_path.resolve(strict=False),
        evidence_relative_path="classes/class_1/scan.pdf",
    )
    assert opened_paths == [evidence_path.resolve(strict=False)]
    assert evidence_path.read_bytes() == before_contents
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == (
        before_paths
    )


def test_rejects_missing_evidence_file(tmp_path: Path) -> None:
    with pytest.raises(EvidenceOpeningError, match="does not exist"):
        open_workspace_evidence(tmp_path, "missing.pdf")


def test_rejects_evidence_directory(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    with pytest.raises(EvidenceOpeningError, match="file"):
        open_workspace_evidence(tmp_path, "evidence")


def test_wraps_pds_core_local_open_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_path = tmp_path / "evidence.pdf"
    evidence_path.write_bytes(b"synthetic evidence")

    def fail_to_open(_path: str | Path) -> Path:
        raise LocalOpenError("viewer unavailable")

    monkeypatch.setattr(evidence_opening, "open_local_path", fail_to_open)

    with pytest.raises(EvidenceOpeningError, match="viewer unavailable") as error:
        open_workspace_evidence(tmp_path, "evidence.pdf")

    assert isinstance(error.value.__cause__, LocalOpenError)

"""CLI tests for local evidence opening."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.submissions as cli_submissions
from quillan.evidence_opening import EvidenceOpeningError, OpenedEvidence


def test_open_evidence_uses_active_workspace_and_prints_relative_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative_path = "classes/class_1/scans/evidence.pdf"
    calls: list[tuple[Path, str | Path]] = []

    monkeypatch.setattr(
        cli_submissions, "resolve_workspace_root", lambda: tmp_path
    )

    def open_evidence(
        workspace_root: str | Path,
        evidence_path: str | Path,
    ) -> OpenedEvidence:
        calls.append((Path(workspace_root), evidence_path))
        return OpenedEvidence(
            evidence_path=tmp_path / relative_path,
            evidence_relative_path=relative_path,
        )

    monkeypatch.setattr(
        cli_submissions, "open_workspace_evidence", open_evidence
    )

    assert main(["open-evidence", relative_path]) == 0
    assert calls == [(tmp_path, relative_path)]
    assert capsys.readouterr().out == (
        "Opened evidence file:\n"
        "classes/class_1/scans/evidence.pdf\n"
    )


@pytest.mark.parametrize("evidence_path", ["missing.pdf", "../outside.pdf"])
def test_open_evidence_reports_validation_failure(
    tmp_path: Path,
    evidence_path: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_submissions, "resolve_workspace_root", lambda: tmp_path
    )

    def fail_to_open(
        _workspace_root: str | Path,
        _evidence_path: str | Path,
    ) -> OpenedEvidence:
        raise EvidenceOpeningError("unsafe or missing evidence")

    monkeypatch.setattr(
        cli_submissions, "open_workspace_evidence", fail_to_open
    )

    assert main(["open-evidence", evidence_path]) == 1
    assert "Error: could not open evidence file" in capsys.readouterr().out

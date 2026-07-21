"""Explicit #339 migration gate for legacy routed-evidence filing."""

from datetime import datetime, timezone
from pathlib import Path

import pds_core.scan_retention as core_retention
import pytest

import quillan.evidence_filing as evidence_filing
from quillan.evidence_filing import EvidenceFilingError, file_routed_response_evidence


def test_routed_evidence_gate_never_retains_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "scan.png"
    source.write_bytes(b"source")
    before = tuple(workspace.rglob("*"))

    def forbidden(*_args: object, **_kwargs: object) -> object:
        pytest.fail("#339 gate must not retain or copy a source")

    monkeypatch.setattr(core_retention, "retain_source_scan", forbidden)
    monkeypatch.setattr(evidence_filing, "_copy_exclusive", forbidden)
    with pytest.raises(EvidenceFilingError, match="#339 observation contract"):
        file_routed_response_evidence(
            workspace,
            route_plan=object(),
            source_file_path=source,
            intake_timestamp=datetime.now(timezone.utc),
        )
    assert tuple(workspace.rglob("*")) == before
    assert not (workspace / "scans").exists()

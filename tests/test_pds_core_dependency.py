"""Smoke tests for the local pds-core development dependency."""

from pds_core.identifiers import validate_identifier
from pds_core.pds1 import build_pds1_payload
from pds_core.qr_payload import QrPayload
from pds_core.workspace import resolve_workspace_root


def test_pds_core_dependency_is_available() -> None:
    assert validate_identifier("english12_p4") == "english12_p4"
    assert QrPayload.__module__ == "pds_core.qr_payload"
    assert callable(resolve_workspace_root)
    assert callable(build_pds1_payload)

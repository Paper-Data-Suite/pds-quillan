"""Tests for Quillan's stable PDS2 integration constants."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pds_core.identifiers import validate_identifier
from pds_core.module_profiles import CORE_ROUTING_CONTRACT_VERSION
from pds_core.routing_models import (
    PDS2_SCHEMA,
    ROUTE_REGISTRATION_SCHEMA_VERSION,
    ModuleRecordRef,
)

from quillan.pds_contract import (
    DISPATCHABLE_ROUTE_STATUSES,
    QUILLAN_DISPLAY_NAME,
    QUILLAN_MODULE_ID,
    RESPONSE_PAGE_CONTRACT_VERSION,
    RESPONSE_PAGE_RECORD_KIND,
    SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS,
    SUPPORTED_QR_SCHEMAS,
    SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS,
)
import quillan.pds_contract as pds_contract

PUBLIC_CONTRACT_CONSTANTS = {
    "DISPATCHABLE_ROUTE_STATUSES",
    "QUILLAN_DISPLAY_NAME",
    "QUILLAN_MODULE_ID",
    "RESPONSE_PAGE_CONTRACT_VERSION",
    "RESPONSE_PAGE_RECORD_KIND",
    "SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS",
    "SUPPORTED_QR_SCHEMAS",
    "SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS",
}


def test_quillan_contract_has_approved_values() -> None:
    assert QUILLAN_MODULE_ID == "quillan"
    assert QUILLAN_DISPLAY_NAME == "Quillan"
    assert RESPONSE_PAGE_RECORD_KIND == "response_page"
    assert RESPONSE_PAGE_CONTRACT_VERSION == "1"
    assert SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS == frozenset(
        {CORE_ROUTING_CONTRACT_VERSION}
    )
    assert SUPPORTED_QR_SCHEMAS == frozenset({PDS2_SCHEMA})
    assert SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS == frozenset(
        {ROUTE_REGISTRATION_SCHEMA_VERSION}
    )
    assert DISPATCHABLE_ROUTE_STATUSES == frozenset({"active"})


def test_contract_exports_exactly_the_public_constants() -> None:
    assert len(pds_contract.__all__) == len(PUBLIC_CONTRACT_CONSTANTS)
    assert set(pds_contract.__all__) == PUBLIC_CONTRACT_CONSTANTS


@pytest.mark.parametrize(
    "collection",
    [
        SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS,
        SUPPORTED_QR_SCHEMAS,
        SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS,
        DISPATCHABLE_ROUTE_STATUSES,
    ],
)
def test_compatibility_collections_are_immutable(collection: frozenset[str]) -> None:
    assert isinstance(collection, frozenset)
    assert not hasattr(collection, "add")
    hash(collection)


def test_response_page_target_is_valid_for_core_models() -> None:
    assert validate_identifier(QUILLAN_MODULE_ID) == QUILLAN_MODULE_ID
    assert validate_identifier(RESPONSE_PAGE_RECORD_KIND) == RESPONSE_PAGE_RECORD_KIND

    target = ModuleRecordRef(
        module_id=QUILLAN_MODULE_ID,
        record_kind=RESPONSE_PAGE_RECORD_KIND,
        record_id="synthetic_response_page_1",
        contract_version=RESPONSE_PAGE_CONTRACT_VERSION,
    )

    assert target.module_id == QUILLAN_MODULE_ID
    assert target.record_kind == RESPONSE_PAGE_RECORD_KIND
    assert target.record_id == "synthetic_response_page_1"
    assert target.contract_version == RESPONSE_PAGE_CONTRACT_VERSION


def test_contract_import_has_no_output_or_workspace_side_effects(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace-must-not-exist"
    environment = os.environ.copy()
    environment["PDS_WORKSPACE_ROOT"] = str(workspace)

    result = subprocess.run(
        [sys.executable, "-c", "import quillan.pds_contract"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert not workspace.exists()

"""Stable Quillan-owned boundary for future PDS2 integration contracts."""

from typing import Final

from pds_core.module_profiles import CORE_ROUTING_CONTRACT_VERSION
from pds_core.routing_models import (
    PDS2_SCHEMA,
    ROUTE_REGISTRATION_SCHEMA_VERSION,
)

QUILLAN_MODULE_ID: Final[str] = "quillan"
QUILLAN_DISPLAY_NAME: Final[str] = "Quillan"

RESPONSE_PAGE_RECORD_KIND: Final[str] = "response_page"
RESPONSE_PAGE_CONTRACT_VERSION: Final[str] = "1"

SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS: Final[frozenset[str]] = frozenset(
    {CORE_ROUTING_CONTRACT_VERSION}
)
SUPPORTED_QR_SCHEMAS: Final[frozenset[str]] = frozenset({PDS2_SCHEMA})
SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {ROUTE_REGISTRATION_SCHEMA_VERSION}
)
DISPATCHABLE_ROUTE_STATUSES: Final[frozenset[str]] = frozenset({"active"})

__all__ = [
    "DISPATCHABLE_ROUTE_STATUSES",
    "QUILLAN_DISPLAY_NAME",
    "QUILLAN_MODULE_ID",
    "RESPONSE_PAGE_CONTRACT_VERSION",
    "RESPONSE_PAGE_RECORD_KIND",
    "SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS",
    "SUPPORTED_QR_SCHEMAS",
    "SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS",
]

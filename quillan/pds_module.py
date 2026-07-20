"""Side-effect-free installed Quillan module profile."""

from __future__ import annotations

import re
from typing import Final

from pds_core.identifiers import validate_identifier
from pds_core.module_profiles import ModuleProfile, validate_module_profile
from pds_core.routing_models import (
    PDS2_SCHEMA,
    ROUTE_REGISTRATION_SCHEMA_VERSION,
    RouteRegistration,
    validate_route_registration,
)

from quillan.module_errors import QuillanRegistrationValidationError
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
from quillan.printable_response_records import validate_issuance_id, validate_page_id

_DETAIL_KEYS: Final[frozenset[str]] = frozenset(
    {"issuance_id", "logical_page", "total_pages"}
)
_FALLBACK: Final[re.Pattern[str]] = re.compile(
    r"Quillan \| class=([^ |]+) \| assignment=([^ |]+) "
    r"\| student=([^ |]+) \| page=([0-9]+)/([0-9]+) "
    r"\| page_id=([^ |]+)"
)


def validate_quillan_registration(registration: RouteRegistration, /) -> None:
    """Validate Quillan's exact, nonwriting response-page route structure."""
    try:
        if not isinstance(registration, RouteRegistration):
            raise ValueError("registration must be a RouteRegistration.")
        validate_route_registration(registration)
        if registration.schema_version != ROUTE_REGISTRATION_SCHEMA_VERSION:
            raise ValueError("registration schema_version must be '1'.")
        locator = registration.locator
        if locator.schema != PDS2_SCHEMA:
            raise ValueError("locator schema must be 'PDS2'.")
        if locator.module_id != QUILLAN_MODULE_ID:
            raise ValueError("locator module_id must be 'quillan'.")
        from quillan.printable_response_routes import validate_route_id

        validate_route_id(locator.route_id)
        if registration.status != "active":
            raise ValueError("registration status must be 'active'.")

        target = registration.target
        if target.module_id != QUILLAN_MODULE_ID:
            raise ValueError("target module_id must be 'quillan'.")
        if target.record_kind != RESPONSE_PAGE_RECORD_KIND:
            raise ValueError("target record_kind must be 'response_page'.")
        if target.contract_version != RESPONSE_PAGE_CONTRACT_VERSION:
            raise ValueError("target contract_version must be '1'.")
        validate_page_id(target.record_id)

        details = registration.module_details
        if frozenset(details) != _DETAIL_KEYS or len(details) != len(_DETAIL_KEYS):
            raise ValueError(
                "module_details must contain exactly issuance_id, logical_page, "
                "and total_pages."
            )
        issuance_id = validate_issuance_id(details["issuance_id"])
        logical_page = _positive_integer(details["logical_page"], "logical_page")
        total_pages = _positive_integer(details["total_pages"], "total_pages")
        if logical_page > total_pages:
            raise ValueError("logical_page must not exceed total_pages.")

        match = _FALLBACK.fullmatch(registration.human_fallback)
        if match is None:
            raise ValueError("human_fallback does not use Quillan's exact grammar.")
        class_id, assignment_id, student_id, logical, total, page_id = match.groups()
        validate_identifier(class_id, "fallback class_id")
        validate_identifier(assignment_id, "fallback assignment_id")
        validate_identifier(student_id, "fallback student_id")
        validate_page_id(page_id)
        if class_id != locator.class_id:
            raise ValueError("fallback class does not match the locator.")
        if assignment_id != locator.work_id:
            raise ValueError("fallback assignment does not match the locator.")
        if page_id != target.record_id:
            raise ValueError("fallback page_id does not match the target.")
        if logical != str(logical_page) or total != str(total_pages):
            raise ValueError("fallback page meaning does not match module_details.")
        # Keep the validated value live so static analysis catches contract drift.
        if not issuance_id:
            raise ValueError("issuance_id must not be empty.")
    except QuillanRegistrationValidationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise QuillanRegistrationValidationError(
            f"Invalid Quillan route registration: {error}"
        ) from error
    return None


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


def get_module_profile() -> ModuleProfile:
    """Return a newly constructed, validated, immutable Quillan profile."""
    from quillan.route_handler import handle_quillan_response_page_route

    return validate_module_profile(
        ModuleProfile(
            module_id=QUILLAN_MODULE_ID,
            display_name=QUILLAN_DISPLAY_NAME,
            supported_core_routing_contract_versions=(
                SUPPORTED_CORE_ROUTING_CONTRACT_VERSIONS
            ),
            supported_qr_schemas=SUPPORTED_QR_SCHEMAS,
            supported_route_registration_schema_versions=(
                SUPPORTED_ROUTE_REGISTRATION_SCHEMA_VERSIONS
            ),
            dispatchable_route_statuses=DISPATCHABLE_ROUTE_STATUSES,
            route_handler=handle_quillan_response_page_route,
            registration_validator=validate_quillan_registration,
        )
    )


__all__ = ["get_module_profile", "validate_quillan_registration"]

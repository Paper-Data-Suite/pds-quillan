"""Focused installed-profile and structural registration tests."""

import copy
from dataclasses import FrozenInstanceError, replace
import inspect
from pathlib import Path

from pds_core.module_profiles import ModuleProfile, validate_module_profile
from pds_core.routing_models import (
    ModuleWorkRef,
    RouteLocator,
    RouteRegistration,
)
import pytest

from quillan.module_errors import QuillanRegistrationValidationError
from quillan.pds_module import get_module_profile, validate_quillan_registration
from quillan.printable_response_routes import build_printable_response_page_route
from tests.test_printable_response_records import record_set


def valid_registration() -> RouteRegistration:
    return build_printable_response_page_route(
        record_set(pages=1).pages[0],
        "rt_0123456789abcdef0123456789abcdef",
    ).registration


def forged(value: object, **changes: object) -> object:
    result = copy.copy(value)
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def rebuilt(
    *,
    details: dict[str, object] | None = None,
    fallback: str | None = None,
    status: str | None = None,
) -> RouteRegistration:
    registration = valid_registration()
    return RouteRegistration(
        registration.schema_version,
        registration.locator,
        registration.target,
        registration.created_at,
        registration.status if status is None else status,
        registration.human_fallback if fallback is None else fallback,
        registration.module_details if details is None else details,  # type: ignore[arg-type]
    )


def test_provider_is_zero_argument_exact_and_immutable() -> None:
    assert len(inspect.signature(get_module_profile).parameters) == 0
    profile = get_module_profile()
    assert isinstance(profile, ModuleProfile)
    assert validate_module_profile(profile) is profile
    assert profile.module_id == "quillan"
    assert profile.display_name == "Quillan"
    assert profile.supported_core_routing_contract_versions == frozenset({"1"})
    assert profile.supported_qr_schemas == frozenset({"PDS2"})
    assert profile.supported_route_registration_schema_versions == frozenset({"1"})
    assert profile.dispatchable_route_statuses == frozenset({"active"})
    assert get_module_profile() == profile
    with pytest.raises(FrozenInstanceError):
        profile.module_id = "other"  # type: ignore[misc]


def test_registration_validator_accepts_exact_route_and_returns_none() -> None:
    registration = valid_registration()
    before = registration.module_details
    result = validate_quillan_registration(registration)  # type: ignore[func-returns-value]
    assert result is None
    assert registration == valid_registration()
    assert registration.module_details == before


@pytest.mark.parametrize("invalid", [None, object(), True, "route"])
def test_registration_validator_has_one_typed_failure(invalid: object) -> None:
    with pytest.raises(QuillanRegistrationValidationError):
        validate_quillan_registration(invalid)  # type: ignore[arg-type]


def invalid_registrations() -> tuple[object, ...]:
    registration = valid_registration()
    locator = registration.locator
    target = registration.target
    fallback = registration.human_fallback
    details = registration.module_details
    wrong_qr_locator = forged(locator, schema="PDS1")
    wrong_module_locator = RouteLocator(
        schema="PDS2",
        work=ModuleWorkRef("other", locator.class_id, locator.work_id),
        route_id=locator.route_id,
    )
    return (
        forged(registration, schema_version="2"),
        forged(registration, locator=wrong_qr_locator),
        forged(registration, locator=wrong_module_locator),
        rebuilt(status="inactive"),
        rebuilt(status="retired"),
        forged(registration, target=forged(target, module_id="other")),
        replace(registration, target=replace(target, record_kind="other")),
        replace(registration, target=replace(target, contract_version="2")),
        forged(registration, target=forged(target, record_id="bad")),
        replace(
            registration,
            target=replace(target, record_id=str(details["issuance_id"])),
        ),
        replace(registration, target=replace(target, record_id=locator.route_id)),
        rebuilt(details={key: value for key, value in details.items() if key != "issuance_id"}),
        rebuilt(details={**details, "extra": 1}),
        rebuilt(details={**details, "issuance_id": "bad"}),
        rebuilt(details={**details, "logical_page": True}),
        rebuilt(details={**details, "total_pages": True}),
        rebuilt(details={**details, "logical_page": 0}),
        rebuilt(details={**details, "total_pages": 0}),
        rebuilt(details={**details, "logical_page": -1}),
        rebuilt(details={**details, "total_pages": -1}),
        rebuilt(details={**details, "logical_page": 2, "total_pages": 1}),
        rebuilt(fallback="malformed"),
        forged(registration, human_fallback=" " + fallback),
        forged(registration, human_fallback=fallback + " "),
        forged(registration, human_fallback=fallback + "\nextra"),
        forged(registration, human_fallback=fallback + "\x00"),
        rebuilt(fallback=fallback + " | extra=value"),
        rebuilt(
            fallback=fallback.replace(
                "class=english10_p2 | assignment=literary_analysis",
                "assignment=literary_analysis | class=english10_p2",
            )
        ),
        rebuilt(fallback=fallback.replace("class=english10_p2", "class=other")),
        rebuilt(
            fallback=fallback.replace(
                "assignment=literary_analysis", "assignment=other"
            )
        ),
        rebuilt(fallback=fallback.replace("student=00107", "student=../bad")),
        rebuilt(
            fallback=fallback.replace(
                str(target.record_id), "pg_ffffffffffffffffffffffffffffffff"
            )
        ),
        rebuilt(fallback=fallback.replace("page=1/1", "page=2/2")),
        rebuilt(fallback=fallback.replace("page=1/1", "page=1/2")),
    )


@pytest.mark.parametrize("registration", invalid_registrations())
def test_every_registration_field_is_independently_rejected(
    registration: object,
) -> None:
    with pytest.raises(QuillanRegistrationValidationError):
        validate_quillan_registration(registration)  # type: ignore[arg-type]


def test_registration_validator_never_touches_filesystem_or_record_loaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("filesystem or record loading is forbidden")

    monkeypatch.setattr(Path, "exists", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    assert validate_quillan_registration(valid_registration()) is None  # type: ignore[func-returns-value]


@pytest.mark.parametrize(
    "route_id",
    [
        "route_safe",
        "rt_short",
        "rt_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        "rt_0123456789ABCDEF0123456789ABCDEF",
        "pg_0123456789abcdef0123456789abcdef",
    ],
)
def test_registration_requires_canonical_quillan_route_id(route_id: str) -> None:
    registration = valid_registration()
    locator = RouteLocator(
        "PDS2", registration.locator.work, route_id
    )
    invalid = RouteRegistration(
        registration.schema_version,
        locator,
        registration.target,
        registration.created_at,
        registration.status,
        registration.human_fallback,
        registration.module_details,
    )
    with pytest.raises(QuillanRegistrationValidationError):
        validate_quillan_registration(invalid)

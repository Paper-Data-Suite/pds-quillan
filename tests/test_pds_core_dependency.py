"""Smoke tests for the installed PDS Core 0.5 routing contract."""

from pds_core.pds2 import parse_pds2_payload, serialize_pds2_payload
from pds_core.route_ids import generate_route_id
from pds_core.route_registrations import (
    load_route_registration,
    write_route_registration,
)
from pds_core.routes import route_registration_path
from pds_core.routing_models import ModuleWorkRef, RouteLocator, RouteRegistration


def test_pds_core_pds2_dependency_is_available() -> None:
    assert callable(parse_pds2_payload)
    assert callable(serialize_pds2_payload)
    assert callable(generate_route_id)
    assert callable(route_registration_path)
    assert callable(write_route_registration)
    assert callable(load_route_registration)
    assert ModuleWorkRef.__module__ == "pds_core.routing_models"
    assert RouteLocator.__module__ == "pds_core.routing_models"
    assert RouteRegistration.__module__ == "pds_core.routing_models"

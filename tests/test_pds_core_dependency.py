"""Smoke tests for the installed PDS Core 0.6 routing contract."""

import importlib.metadata as metadata

import pds_core

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


def test_installed_core_distribution_and_package_versions_agree() -> None:
    assert metadata.version("pds-core") == "0.6.0"
    assert pds_core.__version__ == "0.6.0"

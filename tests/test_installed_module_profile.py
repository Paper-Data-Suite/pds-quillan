"""Installed entry-point and Core one-page dispatch integration."""

from importlib import metadata
from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys

import pds_core.module_dispatch as core_dispatch
from pds_core.module_dispatch import (
    ModuleContractCompatibilityError,
    ModuleRegistrationValidationError,
    ModuleRouteHandlingError,
    RouteDispatchRequest,
    RouteStatusNotDispatchableError,
    dispatch_route,
)
from pds_core.module_profiles import (
    ModuleRegistry,
    ModuleRegistryError,
    UnsupportedModuleError,
    build_module_registry,
)
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef, RouteLocator, RouteRegistration
import pytest

from quillan.module_errors import (
    QuillanRegistrationValidationError,
    QuillanTargetIntegrityError,
)
from quillan.pds_module import get_module_profile
import quillan.route_handler as quillan_handler
from quillan.route_handler import handle_quillan_response_page_route
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from tests.test_route_handler import route_context


def test_project_declares_exact_installed_entry_point() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert text.count('[project.entry-points."paper_data_suite.modules"]') == 1
    assert text.count('quillan = "quillan.pds_module:get_module_profile"') == 1


def test_installed_metadata_has_exact_quillan_entry_point() -> None:
    entries = tuple(
        entry
        for entry in metadata.entry_points(group="paper_data_suite.modules")
        if entry.name == "quillan"
    )
    assert len(entries) == 1
    assert entries[0].value == "quillan.pds_module:get_module_profile"


def test_core_dispatch_preserves_typed_result(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    write_route_registration(tmp_path, resolution.registration)
    profile = get_module_profile()
    success = dispatch_route(
        tmp_path,
        ModuleRegistry((profile,)),
        RouteDispatchRequest(resolution.locator, source, 1),
    )
    assert success.profile == profile
    assert isinstance(success.module_result, QuillanResponsePageDispatchResult)
    assert success.module_result.page_id == resolution.registration.target.record_id


def test_installed_discovery_dispatches_one_quillan_page(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    write_route_registration(tmp_path, resolution.registration)
    success = dispatch_route(
        tmp_path,
        build_module_registry(discover_installed=True),
        RouteDispatchRequest(resolution.locator, source, 1),
    )
    assert success.profile == get_module_profile()
    assert isinstance(success.module_result, QuillanResponsePageDispatchResult)


def rebuild_registration(
    registration: RouteRegistration,
    *,
    target: ModuleRecordRef | None = None,
    status: str | None = None,
) -> RouteRegistration:
    return RouteRegistration(
        registration.schema_version,
        registration.locator,
        registration.target if target is None else target,
        registration.created_at,
        registration.status if status is None else status,
        registration.human_fallback,
        registration.module_details,
    )


def test_validator_failure_is_wrapped_with_quillan_cause(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    invalid = rebuild_registration(
        resolution.registration,
        target=replace(resolution.registration.target, record_kind="other"),
    )
    write_route_registration(tmp_path, invalid)
    with pytest.raises(ModuleRegistrationValidationError) as captured:
        dispatch_route(
            tmp_path,
            ModuleRegistry((get_module_profile(),)),
            RouteDispatchRequest(resolution.locator, source, 1),
        )
    assert isinstance(captured.value.__cause__, QuillanRegistrationValidationError)


def test_handler_failure_is_wrapped_with_typed_cause(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    write_route_registration(tmp_path, resolution.registration)
    page_path = resolution.work_root / "response_pages" / "pages" / (
        resolution.registration.target.record_id + ".json"
    )
    page_path.unlink()
    with pytest.raises(ModuleRouteHandlingError) as captured:
        dispatch_route(
            tmp_path,
            ModuleRegistry((get_module_profile(),)),
            RouteDispatchRequest(resolution.locator, source, 1),
        )
    assert isinstance(captured.value.__cause__, QuillanTargetIntegrityError)


def test_inactive_route_is_rejected_before_handler(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    write_route_registration(
        tmp_path, rebuild_registration(resolution.registration, status="inactive")
    )
    calls = 0

    def forbidden(*_args: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("handler must not run")

    profile = replace(get_module_profile(), route_handler=forbidden)
    with pytest.raises(RouteStatusNotDispatchableError):
        dispatch_route(
            tmp_path,
            ModuleRegistry((profile,)),
            RouteDispatchRequest(resolution.locator, source, 1),
        )
    assert calls == 0


@pytest.mark.parametrize(
    "profile",
    [
        replace(
            get_module_profile(),
            supported_core_routing_contract_versions=frozenset({"999"}),
        ),
        replace(get_module_profile(), supported_qr_schemas=frozenset({"OTHER"})),
    ],
)
def test_preload_contract_rejection_occurs_before_route_loading(
    tmp_path: Path, profile: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)

    def forbidden(*_args: object) -> object:
        raise AssertionError("route loading must not occur")

    monkeypatch.setattr(core_dispatch, "resolve_route_registration", forbidden)
    with pytest.raises(ModuleContractCompatibilityError):
        dispatch_route(
            tmp_path,
            ModuleRegistry((profile,)),  # type: ignore[arg-type]
            RouteDispatchRequest(resolution.locator, source, 1),
        )


def test_wrong_module_and_discovery_disabled_never_invoke_quillan(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    other_locator = RouteLocator(
        "PDS2",
        ModuleWorkRef("other", resolution.locator.class_id, resolution.locator.work_id),
        resolution.locator.route_id,
    )
    registry = build_module_registry(discover_installed=False)
    assert registry.module_ids() == ()
    with pytest.raises(UnsupportedModuleError):
        dispatch_route(
            tmp_path,
            registry,
            RouteDispatchRequest(other_locator, source, 1),
        )


def test_explicit_plus_installed_profile_remains_duplicate_error() -> None:
    with pytest.raises(ModuleRegistryError):
        build_module_registry(
            explicit_profiles=(get_module_profile(),), discover_installed=True
        )


def test_core_returns_handler_result_object_unchanged(tmp_path: Path) -> None:
    resolution, source = route_context(tmp_path)
    write_route_registration(tmp_path, resolution.registration)
    returned: list[QuillanResponsePageDispatchResult] = []

    def recording_handler(*args: object) -> QuillanResponsePageDispatchResult:
        result = handle_quillan_response_page_route(*args)  # type: ignore[arg-type]
        returned.append(result)
        return result

    profile = replace(get_module_profile(), route_handler=recording_handler)
    success = dispatch_route(
        tmp_path,
        ModuleRegistry((profile,)),
        RouteDispatchRequest(resolution.locator, source, 1),
    )
    assert success.module_result is returned[0]


@pytest.mark.parametrize(
    "statement",
    [
        "import quillan.pds_module",
        (
            "from quillan.pds_module import get_module_profile; "
            "first=get_module_profile(); second=get_module_profile(); "
            "assert first == second"
        ),
    ],
)
def test_provider_import_is_silent_and_safe_outside_workspace(
    tmp_path: Path, statement: str
) -> None:
    forbidden = {
        "quillan.cli",
        "quillan.cli_app",
        "quillan.payload_validation",
        "quillan.routing_review",
        "pds_core.pds1",
        "pds_core.qr_payload",
        "cv2",
        "pdf2image",
        "reportlab",
        "qrcode",
    }
    code = (
        "import os,sys; before=os.getcwd(); "
        f"{statement}; "
        f"forbidden={forbidden!r}; "
        "assert forbidden.isdisjoint(sys.modules); "
        "assert os.getcwd()==before"
    )
    before = tuple(tmp_path.iterdir())
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert tuple(tmp_path.iterdir()) == before


def test_noncanonical_safe_route_id_fails_in_quillan_validator_before_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolution, source = route_context(tmp_path)
    locator = RouteLocator(
        "PDS2", resolution.locator.work, "route_safe"
    )
    registration = RouteRegistration(
        resolution.registration.schema_version,
        locator,
        resolution.registration.target,
        resolution.registration.created_at,
        resolution.registration.status,
        resolution.registration.human_fallback,
        resolution.registration.module_details,
    )
    write_route_registration(tmp_path, registration)
    handler_calls = 0
    retained_calls = 0

    def forbidden_handler(*_args: object) -> object:
        nonlocal handler_calls
        handler_calls += 1
        raise AssertionError("handler must not run")

    def forbidden_retained(*_args: object, **_kwargs: object) -> object:
        nonlocal retained_calls
        retained_calls += 1
        raise AssertionError("retained validation must not run")

    monkeypatch.setattr(
        quillan_handler, "validate_quillan_retained_source", forbidden_retained
    )
    profile = replace(get_module_profile(), route_handler=forbidden_handler)
    with pytest.raises(ModuleRegistrationValidationError) as captured:
        dispatch_route(
            tmp_path,
            ModuleRegistry((profile,)),
            RouteDispatchRequest(locator, source, 1),
        )
    assert isinstance(captured.value.__cause__, QuillanRegistrationValidationError)
    assert handler_calls == 0
    assert retained_calls == 0

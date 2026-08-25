from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from pds_core.module_dispatch import (
    RouteDispatchFailure,
    RouteDispatchRequest,
    RouteDispatchSuccess,
    dispatch_routes,
)
from pds_core.module_profiles import (
    CORE_ROUTING_CONTRACT_VERSION,
    ModuleProfile,
    ModuleRegistry,
)
from pds_core.route_registrations import write_route_registration
from pds_core.routing_models import (
    ModuleRecordRef,
    ModuleWorkRef,
    PDS2_SCHEMA,
    ROUTE_REGISTRATION_SCHEMA_VERSION,
    RouteLocator,
    RouteRegistration,
    RouteResolution,
)
from pds_core.scan_retention import RetainedSourceScan

from quillan.pds_module import get_module_profile
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from tests.test_route_handler import route_context


_FOREIGN_MODULE_ID = "synthetic"
_FOREIGN_SECRET = "foreign-private-payload-must-remain-opaque"


def _foreign_registration(class_id: str) -> RouteRegistration:
    work = ModuleWorkRef(
        module_id=_FOREIGN_MODULE_ID,
        class_id=class_id,
        work_id="foreign_work",
    )
    return RouteRegistration(
        schema_version=ROUTE_REGISTRATION_SCHEMA_VERSION,
        locator=RouteLocator(
            schema=PDS2_SCHEMA,
            work=work,
            route_id="foreign_route",
        ),
        target=ModuleRecordRef(
            module_id=_FOREIGN_MODULE_ID,
            record_kind="foreign_record",
            record_id="foreign_record_1",
            contract_version="1",
        ),
        created_at="2026-08-25T00:00:00+00:00",
        status="active",
        human_fallback="Synthetic foreign module route",
        module_details={"private_marker": _FOREIGN_SECRET},
    )


def _foreign_profile(calls: list[str]) -> ModuleProfile:
    def validate_foreign(registration: RouteRegistration, /) -> None:
        assert registration.locator.module_id == _FOREIGN_MODULE_ID
        assert registration.target.module_id == _FOREIGN_MODULE_ID

    def handle_foreign(
        resolution: RouteResolution,
        retained_source: RetainedSourceScan,
        source_page_number: int,
        /,
    ) -> object:
        assert resolution.locator.module_id == _FOREIGN_MODULE_ID
        assert retained_source.retained_source_path.is_file()
        assert source_page_number == 2
        calls.append(resolution.locator.route_id)
        return {
            "module_id": _FOREIGN_MODULE_ID,
            "route_id": resolution.locator.route_id,
        }

    return ModuleProfile(
        module_id=_FOREIGN_MODULE_ID,
        display_name="Synthetic Foreign Module",
        supported_core_routing_contract_versions=frozenset(
            {CORE_ROUTING_CONTRACT_VERSION}
        ),
        supported_qr_schemas=frozenset({PDS2_SCHEMA}),
        supported_route_registration_schema_versions=frozenset(
            {ROUTE_REGISTRATION_SCHEMA_VERSION}
        ),
        dispatchable_route_statuses=frozenset({"active"}),
        route_handler=handle_foreign,
        registration_validator=validate_foreign,
    )


def _tracked_quillan_profile(calls: list[str]) -> ModuleProfile:
    original = get_module_profile()

    def handle_quillan(
        resolution: RouteResolution,
        retained_source: RetainedSourceScan,
        source_page_number: int,
        /,
    ) -> object:
        assert resolution.locator.module_id == "quillan"
        calls.append(resolution.locator.route_id)
        return original.route_handler(
            resolution,
            retained_source,
            source_page_number,
        )

    return replace(original, route_handler=handle_quillan)


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_mixed_core_dispatch_calls_only_each_routes_owning_module(
    tmp_path: Path,
) -> None:
    quillan_resolution, retained = route_context(tmp_path)
    write_route_registration(tmp_path, quillan_resolution.registration)

    foreign = _foreign_registration(quillan_resolution.locator.class_id)
    write_route_registration(tmp_path, foreign)

    foreign_sentinel = (
        tmp_path
        / "classes"
        / foreign.locator.class_id
        / "modules"
        / _FOREIGN_MODULE_ID
        / "private"
        / "sentinel.txt"
    )
    foreign_sentinel.parent.mkdir(parents=True, exist_ok=True)
    foreign_sentinel.write_text(_FOREIGN_SECRET, encoding="utf-8")

    quillan_calls: list[str] = []
    foreign_calls: list[str] = []
    registry = ModuleRegistry(
        (
            _tracked_quillan_profile(quillan_calls),
            _foreign_profile(foreign_calls),
        )
    )

    before = _file_snapshot(tmp_path)
    outcomes = dispatch_routes(
        tmp_path,
        registry,
        (
            RouteDispatchRequest(
                locator=foreign.locator,
                retained_source=retained,
                source_page_number=2,
            ),
            RouteDispatchRequest(
                locator=quillan_resolution.locator,
                retained_source=retained,
                source_page_number=1,
            ),
        ),
    )
    after = _file_snapshot(tmp_path)

    assert len(outcomes) == 2
    foreign_outcome = cast(RouteDispatchSuccess, outcomes[0])
    quillan_outcome = cast(RouteDispatchSuccess, outcomes[1])
    assert isinstance(foreign_outcome, RouteDispatchSuccess)
    assert isinstance(quillan_outcome, RouteDispatchSuccess)

    assert foreign_outcome.profile.module_id == _FOREIGN_MODULE_ID
    assert foreign_outcome.resolution.locator.module_id == _FOREIGN_MODULE_ID
    assert foreign_outcome.module_result == {
        "module_id": _FOREIGN_MODULE_ID,
        "route_id": foreign.locator.route_id,
    }

    assert quillan_outcome.profile.module_id == "quillan"
    assert quillan_outcome.resolution.locator.module_id == "quillan"
    assert isinstance(
        quillan_outcome.module_result,
        QuillanResponsePageDispatchResult,
    )
    assert quillan_outcome.module_result.route_id == quillan_resolution.locator.route_id

    assert foreign_calls == [foreign.locator.route_id]
    assert quillan_calls == [quillan_resolution.locator.route_id]
    assert foreign_sentinel.read_text(encoding="utf-8") == _FOREIGN_SECRET
    assert before == after


def test_absent_foreign_module_is_isolated_without_quillan_fallback(
    tmp_path: Path,
) -> None:
    quillan_resolution, retained = route_context(tmp_path)
    write_route_registration(tmp_path, quillan_resolution.registration)

    foreign = _foreign_registration(quillan_resolution.locator.class_id)
    write_route_registration(tmp_path, foreign)

    quillan_calls: list[str] = []
    registry = ModuleRegistry((_tracked_quillan_profile(quillan_calls),))

    before = _file_snapshot(tmp_path)
    outcomes = dispatch_routes(
        tmp_path,
        registry,
        (
            RouteDispatchRequest(
                locator=foreign.locator,
                retained_source=retained,
                source_page_number=2,
            ),
            RouteDispatchRequest(
                locator=quillan_resolution.locator,
                retained_source=retained,
                source_page_number=1,
            ),
        ),
    )
    after = _file_snapshot(tmp_path)

    assert len(outcomes) == 2
    assert isinstance(outcomes[0], RouteDispatchFailure)
    assert isinstance(outcomes[1], RouteDispatchSuccess)
    assert outcomes[0].request.locator.module_id == _FOREIGN_MODULE_ID
    assert outcomes[1].profile.module_id == "quillan"
    assert quillan_calls == [quillan_resolution.locator.route_id]
    assert before == after


def test_quillan_routing_profile_remains_exact_core_v1_pds2_contract() -> None:
    profile = get_module_profile()
    assert profile.module_id == "quillan"
    assert profile.supported_core_routing_contract_versions == frozenset(
        {CORE_ROUTING_CONTRACT_VERSION}
    )
    assert profile.supported_qr_schemas == frozenset({PDS2_SCHEMA})
    assert profile.supported_route_registration_schema_versions == frozenset(
        {ROUTE_REGISTRATION_SCHEMA_VERSION}
    )
    assert profile.dispatchable_route_statuses == frozenset({"active"})

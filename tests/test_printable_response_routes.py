"""PDS2 route contract tests for printable response pages."""

from dataclasses import replace
import importlib
from pathlib import Path
import subprocess
import sys

from pds_core.pds2 import parse_pds2_payload
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef, RouteLocator
import pytest

from quillan.printable_response_routes import (
    PrintableResponseRouteError,
    PrintableResponseRouteIntegrityError,
    PrintableResponseRoutePersistenceError,
    PrintableResponseRouteValidationError,
    PrintableResponseRouteDestinationError,
    build_printable_response_page_route,
    build_printable_response_route_set,
    persist_printable_response_route_set,
    preflight_printable_response_route_collection,
    preflight_printable_response_route_destinations,
    validate_registered_printable_response_route_set,
    validate_route_id,
)
from quillan.printable_response_generation import (
    build_printable_response_artifact_plan,
    select_printable_response_predecessors,
)
from quillan.printable_response_packet import plan_printable_response_packet
from quillan.printable_response_persistence import (
    PersistedPrintableResponseRecordSet,
    transition_printable_response_issuance,
    write_printable_response_record_set,
)
from quillan.work_paths import (
    initialize_managed_work_layout,
    quillan_work_paths,
)
from typing import Any
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)
from tests.test_printable_response_records import PAGE_IDS, record_set

route_service: Any = importlib.import_module("quillan.printable_response_routes")

ROUTE_IDS = (
    "rt_0123456789abcdef0123456789abcdef",
    "rt_1123456789abcdef0123456789abcdef",
    "rt_2123456789abcdef0123456789abcdef",
)


@pytest.mark.parametrize("invalid_root", [None, object(), 42, []])
@pytest.mark.parametrize(
    "operation",
    [
        lambda root: preflight_printable_response_route_collection(root, object()),
        lambda root: preflight_printable_response_route_destinations(root, object()),
        lambda root: validate_registered_printable_response_route_set(
            root, object(), object()
        ),
        lambda root: persist_printable_response_route_set(
            root, object(), object(), object()
        ),
    ],
)
def test_all_public_route_apis_reject_wrong_root_types_without_leaking(
    tmp_path: Path, invalid_root: object, operation: Any
) -> None:
    with pytest.raises(PrintableResponseRouteDestinationError, match="workspace_root"):
        operation(invalid_root)
    assert tuple(tmp_path.iterdir()) == ()


def test_exact_route_and_registration_contract(tmp_path: Path) -> None:
    page = record_set(pages=1).pages[0]
    route = build_printable_response_page_route(page, ROUTE_IDS[0])
    assert route.locator.work == ModuleWorkRef(
        "quillan", page.class_id, page.assignment_id
    )
    assert route.registration.target == ModuleRecordRef(
        "quillan", "response_page", PAGE_IDS[0], "1"
    )
    assert route.registration.created_at == page.created_at
    assert route.registration.status == "active"
    assert route.registration.human_fallback == (
        "Quillan | class=english10_p2 | assignment=literary_analysis "
        "| student=00107 | page=1/1 "
        f"| page_id={PAGE_IDS[0]}"
    )
    assert route.registration.module_details == {
        "issuance_id": page.issuance_id,
        "logical_page": 1,
        "total_pages": 1,
    }
    assert parse_pds2_payload(route.payload_text) == route.locator
    assert "00107" not in route.payload_text
    assert PAGE_IDS[0] not in route.payload_text
    assert preflight_printable_response_route_destinations(tmp_path, (route,))[0].name == (
        ROUTE_IDS[0] + ".json"
    )


def test_route_set_preserves_page_order_and_uniqueness() -> None:
    records = record_set()
    routes = build_printable_response_route_set(records, ROUTE_IDS)
    assert tuple(route.page for route in routes) == records.pages
    assert tuple(route.locator.route_id for route in routes) == ROUTE_IDS


def planned_artifact(tmp_path: Path):  # type: ignore[no-untyped-def]
    packet = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    predecessors = select_printable_response_predecessors(
        packet.workspace_root, packet.work_ref, packet.students
    )
    return packet, build_printable_response_artifact_plan(
        workspace_root=packet.workspace_root,
        work_ref=packet.work_ref,
        assignment=packet.assignment,
        students=packet.students,
        pages_per_student=1,
        output_path=packet.output_path,
        predecessors=predecessors,
    )


def test_public_route_persistence_requires_exact_durable_records(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact = planned_artifact(tmp_path)
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    records = artifact.record_sets[0]
    claimed_persisted = PersistedPrintableResponseRecordSet(
        records,
        tmp_path / "missing-issuance.json",
        tuple(tmp_path / f"missing-{page.page_id}.json" for page in records.pages),
    )
    with pytest.raises(PrintableResponseRouteIntegrityError):
        persist_printable_response_route_set(
            tmp_path, packet.work_ref, claimed_persisted, artifact.route_sets[0]
        )
    assert not tuple((artifact.output_path.parent.parent / "routes").glob("*.json"))
    persisted = write_printable_response_record_set(
        tmp_path, packet.work_ref, artifact.record_sets[0]
    )
    result = persist_printable_response_route_set(
        tmp_path, packet.work_ref, persisted, artifact.route_sets[0]
    )
    assert result.record_set == persisted.record_set
    assert tuple(item.route for item in result.routes) == artifact.route_sets[0]
    assert all(item.registration_path.is_file() for item in result.routes)


def test_route_persistence_rejects_wrong_durable_lifecycle(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact = planned_artifact(tmp_path)
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    persisted = write_printable_response_record_set(
        tmp_path, packet.work_ref, artifact.record_sets[0]
    )
    transition_printable_response_issuance(
        tmp_path,
        packet.work_ref,
        persisted.record_set.issuance.issuance_id,
        expected_revision=1,
        new_status="issued",
        timestamp="2030-07-20T00:00:00+00:00",
    )
    with pytest.raises(PrintableResponseRouteIntegrityError):
        persist_printable_response_route_set(
            tmp_path, packet.work_ref, persisted, artifact.route_sets[0]
        )


def test_post_write_exception_reports_current_path_without_claiming_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact = planned_artifact(tmp_path)
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    persisted = write_printable_response_record_set(
        tmp_path, packet.work_ref, artifact.record_sets[0]
    )
    expected = artifact.output_path.parent.parent / "routes" / (
        artifact.route_sets[0][0].locator.route_id + ".json"
    )
    original = route_service.write_route_registration

    def write_then_raise(*args: Any, **kwargs: Any) -> Path:
        original(*args, **kwargs)
        raise OSError("synthetic post-write failure")

    monkeypatch.setattr(route_service, "write_route_registration", write_then_raise)
    with pytest.raises(PrintableResponseRoutePersistenceError) as captured:
        persist_printable_response_route_set(
            tmp_path, packet.work_ref, persisted, artifact.route_sets[0]
        )
    assert captured.value.created_paths == ()
    assert captured.value.verified_routes == ()
    assert captured.value.current_path == expected
    assert captured.value.failed_page_id == artifact.record_sets[0].pages[0].page_id
    assert expected.is_file()
    assert isinstance(captured.value, PrintableResponseRouteError)


@pytest.mark.parametrize("mode", ["reload-error", "equality-mismatch"])
def test_route_reload_failures_report_durable_unverified_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    write_packet_workspace(tmp_path)
    packet, artifact = planned_artifact(tmp_path)
    initialize_managed_work_layout(
        quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    persisted = write_printable_response_record_set(
        tmp_path, packet.work_ref, artifact.record_sets[0]
    )
    expected = artifact.output_path.parent.parent / "routes" / (
        artifact.route_sets[0][0].locator.route_id + ".json"
    )
    if mode == "reload-error":
        monkeypatch.setattr(
            route_service,
            "load_route_registration",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("synthetic registration reload failure")
            ),
        )
    else:
        wrong = build_printable_response_page_route(
            artifact.record_sets[0].pages[0],
            "rt_ffffffffffffffffffffffffffffffff",
        ).registration
        monkeypatch.setattr(
            route_service, "load_route_registration", lambda *_args, **_kwargs: wrong
        )
    with pytest.raises(PrintableResponseRoutePersistenceError) as captured:
        persist_printable_response_route_set(
            tmp_path, packet.work_ref, persisted, artifact.route_sets[0]
        )
    assert captured.value.created_paths == (expected,)
    assert captured.value.verified_routes == ()
    assert captured.value.current_path == expected
    assert expected.is_file()


@pytest.mark.parametrize(
    "tamper",
    [
        lambda route: replace(
            route, registration=replace(route.registration, human_fallback="wrong")
        ),
        lambda route: replace(
            route,
            registration=replace(
                route.registration,
                module_details={**route.registration.module_details, "extra": 1},
            ),
        ),
        lambda route: replace(
            route,
            registration=replace(
                route.registration,
                target=ModuleRecordRef("quillan", "response_page", PAGE_IDS[1], "1"),
            ),
        ),
        lambda route: replace(
            route, registration=replace(route.registration, created_at="2020-01-01T00:00:00+00:00")
        ),
        lambda route: replace(
            route, registration=replace(route.registration, status="inactive")
        ),
        lambda route: replace(route, payload_text=route.payload_text + "x"),
        lambda route: replace(
            route,
            locator=RouteLocator(
                route.locator.schema,
                ModuleWorkRef("quillan", route.page.class_id, "wrong_work"),
                route.locator.route_id,
            ),
        ),
        lambda route: replace(
            route,
            locator=RouteLocator(
                route.locator.schema,
                route.locator.work,
                "rt_ffffffffffffffffffffffffffffffff",
            ),
        ),
    ],
    ids=[
        "human-fallback",
        "module-details-keys",
        "target",
        "timestamp",
        "status",
        "payload",
        "locator-work",
        "route-id",
    ],
)
def test_route_contract_rejects_every_tampered_field(tamper):  # type: ignore[no-untyped-def]
    route = build_printable_response_page_route(
        record_set(pages=1).pages[0], ROUTE_IDS[0]
    )
    with pytest.raises(PrintableResponseRouteValidationError):
        tamper(route)


@pytest.mark.parametrize(
    "invalid", ["rt_ABCDEF0123456789abcdef0123456789", "rt_short", True, None]
)
def test_exact_route_id_validation(invalid: object) -> None:
    with pytest.raises(PrintableResponseRouteValidationError):
        validate_route_id(invalid)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
@pytest.mark.parametrize(
    "relative",
    [
        Path("classes") / "english10_p2" / "modules",
        Path("classes") / "english10_p2" / "modules" / "quillan" / "work",
        Path("classes")
        / "english10_p2"
        / "modules"
        / "quillan"
        / "work"
        / "literary_analysis"
        / "routes",
    ],
    ids=["modules", "work-root", "routes"],
)
def test_route_preflight_rejects_real_windows_junction(
    tmp_path: Path, relative: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    junction = tmp_path / relative
    junction.parent.mkdir(parents=True)
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip(f"Windows junction creation unavailable: {created.stderr}")
    try:
        route = build_printable_response_page_route(
            record_set(pages=1).pages[0], ROUTE_IDS[0]
        )
        with pytest.raises(PrintableResponseRouteDestinationError, match="junction"):
            preflight_printable_response_route_destinations(tmp_path, (route,))
    finally:
        junction.rmdir()
    assert sentinel.read_bytes() == b"unchanged"
    assert tuple(outside.iterdir()) == (sentinel,)

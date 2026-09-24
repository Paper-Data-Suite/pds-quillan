"""Verify installed v0.10.0 release-edge interoperability after full acceptance."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path

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
from pds_core.publication_storage import (
    get_current_publication_record,
    list_publication_record_set,
    load_publication_withdrawal,
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
    route_registration_from_dict,
)
from pds_core.scan_retention import RetainedSourceScan, retain_source_scan

from quillan.academic_result_publication import (
    QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
)
from quillan.diagnostic_events import list_diagnostic_events
from quillan.pds_module import get_module_profile
from quillan.publication_revision_policy import (
    QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
)
from quillan.work_paths import quillan_work_ref

EXPECTED_QUILLAN_VERSION = "0.10.2"
CLASS_ID = "synthetic_release_class"
ASSIGNMENT_ID = "synthetic_release_digital"
FOREIGN_MODULE_ID = "synthetic"
FOREIGN_ROUTE_ID = "issue393_foreign_route"
FOREIGN_SECRET = "foreign-private-payload-must-remain-opaque"

EXPECTED_ENTRY_POINTS = {
    ("console_scripts", "quillan"): "quillan.cli:main",
    (
        "paper_data_suite.modules",
        "quillan",
    ): "quillan.pds_module:get_module_profile",
    (
        "paper_data_suite.publication_producers",
        "quillan",
    ): "quillan.pds_publication:get_publication_producer_profile",
    (
        "paper_data_suite.module_operations",
        "quillan",
    ): "quillan.pds_operations:get_module_operations_profile",
}


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"{module_name} has no import origin")
    return Path(raw).resolve()


def _assert_source_isolation(repository: Path) -> None:
    for module_name in ("quillan", "pds_core"):
        origin = _module_origin(module_name)
        if origin.is_relative_to(repository):
            raise AssertionError(f"{module_name} import is source-shadowed")


def _assert_entry_points() -> None:
    distribution = metadata.distribution("quillan")
    for (group, name), expected in EXPECTED_ENTRY_POINTS.items():
        found = tuple(
            entry
            for entry in distribution.entry_points
            if entry.group == group and entry.name == name
        )
        if len(found) != 1:
            raise AssertionError(
                f"expected exactly one {group}:{name} entry point, got {len(found)}"
            )
        if found[0].value != expected:
            raise AssertionError(
                f"unexpected {group}:{name} target: {found[0].value}"
            )


def _assert_publication_lifecycle(workspace: Path) -> dict[str, object]:
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    series = list_publication_record_set(
        workspace,
        work,
        QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
        QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    )
    if len(series) != 2:
        raise AssertionError(
            f"expected two publication revisions after producer acceptance, got {len(series)}"
        )
    first, head = series
    if head.supersedes_publication_id != first.publication_id:
        raise AssertionError("publication revision 2 does not supersede revision 1")
    if head.record_set_revision != 2:
        raise AssertionError("publication series head is not record-set revision 2")

    current = get_current_publication_record(
        workspace,
        work,
        QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
        QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    )
    if current is not None:
        raise AssertionError("producer acceptance should leave the series withdrawn")
    withdrawal = load_publication_withdrawal(workspace, head.publication_id)
    if withdrawal is None:
        raise AssertionError("withdrawn series head has no canonical withdrawal")

    return {
        "publication_series_revisions": [item.record_set_revision for item in series],
        "publication_supersession_verified": True,
        "publication_withdrawal_verified": True,
        "publication_current_selectable": False,
    }


def _load_existing_quillan_registration(workspace: Path) -> RouteRegistration:
    route_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "routes"
    )
    candidates = tuple(sorted(route_dir.glob("*.json")))
    if not candidates:
        raise AssertionError("installed full workflow produced no Quillan route registrations")
    value = json.loads(candidates[0].read_text(encoding="utf-8", errors="strict"))
    if type(value) is not dict:
        raise AssertionError("Quillan route registration is not a JSON object")
    registration = route_registration_from_dict(value)
    if registration.locator.module_id != "quillan":
        raise AssertionError("selected route registration is not Quillan-owned")
    return registration


def _foreign_registration(class_id: str) -> RouteRegistration:
    work = ModuleWorkRef(
        module_id=FOREIGN_MODULE_ID,
        class_id=class_id,
        work_id="issue393_foreign_work",
    )
    return RouteRegistration(
        schema_version=ROUTE_REGISTRATION_SCHEMA_VERSION,
        locator=RouteLocator(
            schema=PDS2_SCHEMA,
            work=work,
            route_id=FOREIGN_ROUTE_ID,
        ),
        target=ModuleRecordRef(
            module_id=FOREIGN_MODULE_ID,
            record_kind="foreign_record",
            record_id="foreign_record_1",
            contract_version="1",
        ),
        created_at="2026-08-25T21:00:00+00:00",
        status="active",
        human_fallback="Synthetic foreign #393 route",
        module_details={"private_marker": FOREIGN_SECRET},
    )


def _foreign_profile(calls: list[str]) -> ModuleProfile:
    def validate_foreign(registration: RouteRegistration, /) -> None:
        if registration.locator.module_id != FOREIGN_MODULE_ID:
            raise AssertionError("foreign validator received non-foreign registration")
        if registration.target.module_id != FOREIGN_MODULE_ID:
            raise AssertionError("foreign registration target changed ownership")

    def handle_foreign(
        resolution: RouteResolution,
        retained_source: RetainedSourceScan,
        source_page_number: int,
        /,
    ) -> object:
        if resolution.locator.module_id != FOREIGN_MODULE_ID:
            raise AssertionError("foreign handler received non-foreign route")
        if not retained_source.retained_source_path.is_file():
            raise AssertionError("foreign handler lost retained source provenance")
        if source_page_number != 2:
            raise AssertionError("foreign handler received wrong source page number")
        calls.append(resolution.locator.route_id)
        return {
            "module_id": FOREIGN_MODULE_ID,
            "route_id": resolution.locator.route_id,
        }

    return ModuleProfile(
        module_id=FOREIGN_MODULE_ID,
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
    if (
        original.module_id != "quillan"
        or original.supported_core_routing_contract_versions
        != frozenset({CORE_ROUTING_CONTRACT_VERSION})
        or original.supported_qr_schemas != frozenset({PDS2_SCHEMA})
        or original.supported_route_registration_schema_versions
        != frozenset({ROUTE_REGISTRATION_SCHEMA_VERSION})
        or original.dispatchable_route_statuses != frozenset({"active"})
    ):
        raise AssertionError("installed Quillan routing profile changed")

    def track_quillan(
        resolution: RouteResolution,
        retained_source: RetainedSourceScan,
        source_page_number: int,
        /,
    ) -> object:
        if resolution.locator.module_id != "quillan":
            raise AssertionError("Quillan wrapper received foreign route")
        if not retained_source.retained_source_path.is_file():
            raise AssertionError("Quillan wrapper lost retained source provenance")
        if source_page_number != 1:
            raise AssertionError("Quillan wrapper received wrong source page number")
        calls.append(resolution.locator.route_id)
        return {
            "module_id": "quillan",
            "route_id": resolution.locator.route_id,
        }

    # Keep the installed Quillan registration validator and exact advertised
    # compatibility profile. Only the handler is wrapped so this acceptance
    # measures Core ownership/dispatch isolation without replaying Quillan's
    # already-proven route-handler write-free semantics.
    return replace(original, route_handler=track_quillan)


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _mixed_routing(workspace: Path) -> dict[str, object]:
    quillan_registration = _load_existing_quillan_registration(workspace)
    foreign = _foreign_registration(quillan_registration.locator.class_id)
    write_route_registration(workspace, foreign)

    source = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "templates"
        / "printable_response_pages.pdf"
    )
    if not source.is_file():
        raise AssertionError(
            "installed full workflow produced no printable response packet"
        )
    retained = retain_source_scan(
        workspace,
        source,
        intake_timestamp=datetime(2026, 8, 25, 21, 5, tzinfo=timezone.utc),
    )

    sentinel = (
        workspace
        / "classes"
        / foreign.locator.class_id
        / "modules"
        / FOREIGN_MODULE_ID
        / "private"
        / "sentinel.txt"
    )
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(FOREIGN_SECRET, encoding="utf-8")

    quillan_calls: list[str] = []
    foreign_calls: list[str] = []
    both_registry = ModuleRegistry(
        (
            _tracked_quillan_profile(quillan_calls),
            _foreign_profile(foreign_calls),
        )
    )
    requests = (
        RouteDispatchRequest(
            locator=foreign.locator,
            retained_source=retained,
            source_page_number=2,
        ),
        RouteDispatchRequest(
            locator=quillan_registration.locator,
            retained_source=retained,
            source_page_number=1,
        ),
    )

    before = _file_snapshot(workspace)
    both = dispatch_routes(workspace, both_registry, requests)
    after = _file_snapshot(workspace)
    if after != before:
        raise AssertionError("mixed Core dispatch modified workspace state")
    if len(both) != 2:
        raise AssertionError("mixed Core dispatch returned wrong outcome count")
    if not isinstance(both[0], RouteDispatchSuccess):
        raise AssertionError("foreign registered route did not dispatch successfully")
    if not isinstance(both[1], RouteDispatchSuccess):
        raise AssertionError("Quillan registered route did not dispatch successfully")
    if foreign_calls != [FOREIGN_ROUTE_ID]:
        raise AssertionError("foreign module did not receive exactly its own route")
    if quillan_calls != [quillan_registration.locator.route_id]:
        raise AssertionError("Quillan did not receive exactly its own route")
    if sentinel.read_text(encoding="utf-8") != FOREIGN_SECRET:
        raise AssertionError("foreign private state was modified")

    quillan_calls.clear()
    quillan_only = ModuleRegistry((_tracked_quillan_profile(quillan_calls),))
    before_missing = _file_snapshot(workspace)
    missing = dispatch_routes(workspace, quillan_only, requests)
    after_missing = _file_snapshot(workspace)
    if after_missing != before_missing:
        raise AssertionError("missing-foreign dispatch modified workspace state")
    if not isinstance(missing[0], RouteDispatchFailure):
        raise AssertionError("absent foreign module did not fail in isolation")
    if not isinstance(missing[1], RouteDispatchSuccess):
        raise AssertionError("Quillan route failed after foreign-module failure")
    if quillan_calls != [quillan_registration.locator.route_id]:
        raise AssertionError("foreign failure caused Quillan fallback or duplicate dispatch")

    return {
        "mixed_routing_registered": "passed",
        "mixed_routing_missing_foreign": "passed",
        "foreign_fallback_to_quillan": False,
        "quillan_route_after_foreign_failure": True,
        "dispatch_workspace_unchanged": True,
    }


def _diagnostic_privacy(workspace: Path) -> dict[str, object]:
    listing = list_diagnostic_events(workspace, limit=200)
    if not listing.events:
        raise AssertionError("installed acceptance produced no local diagnostics")
    codes = tuple(sorted({event.code for event in listing.events}))
    rendered = json.dumps(
        [
            {
                "component": event.component,
                "workflow": event.workflow,
                "stage": event.stage,
                "outcome": event.outcome,
                "category": event.category,
                "code": event.code,
                "safe_summary": event.safe_summary,
                "path_context": event.path_context,
            }
            for event in listing.events
        ],
        sort_keys=True,
    )
    for forbidden in (
        "Synthetic teacher feedback.",
        "Synthetic matrix feedback.",
        "Synthetic private teacher note.",
        "Synthetic note after export to make feedback stale.",
        FOREIGN_SECRET,
    ):
        if forbidden in rendered:
            raise AssertionError("diagnostic output exposed private acceptance content")
    return {
        "diagnostic_event_count": len(listing.events),
        "diagnostic_codes": list(codes),
        "diagnostic_privacy": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument(
        "--expected-core-version",
        choices=("0.6.2", "0.6.3"),
        required=True,
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve(strict=True)
    repository = args.repository.resolve(strict=True)
    if metadata.version("quillan") != EXPECTED_QUILLAN_VERSION:
        raise AssertionError("installed Quillan version is not v0.10.2")
    if metadata.version("pds-core") != args.expected_core_version:
        raise AssertionError("installed Core version disagrees with endpoint")

    _assert_source_isolation(repository)
    _assert_entry_points()

    result: dict[str, object] = {
        "quillan_version": EXPECTED_QUILLAN_VERSION,
        "core_version": args.expected_core_version,
        "entry_points": {
            f"{group}:{name}": target
            for (group, name), target in EXPECTED_ENTRY_POINTS.items()
        },
        **_assert_publication_lifecycle(workspace),
        **_mixed_routing(workspace),
        **_diagnostic_privacy(workspace),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

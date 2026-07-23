"""Strict PDS2 route planning and persistence for printable response pages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Final

from pds_core.pds2 import Pds2PayloadError, parse_pds2_payload, serialize_pds2_payload
from pds_core.route_registrations import (
    RouteRegistrationPersistenceError,
    RouteRegistrationWriteError,
    load_route_registration,
    write_route_registration,
)
from pds_core.routes import route_registration_path
from pds_core.routing_models import (
    PDS2_SCHEMA,
    ROUTE_REGISTRATION_SCHEMA_VERSION,
    ModuleWorkRef,
    RouteLocator,
    RouteRegistration,
    RoutingModelError,
)

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.printable_response_persistence import (
    PersistedPrintableResponseRecordSet,
    PrintableResponsePersistenceError,
    load_printable_response_record_set,
)
from quillan.printable_response_records import (
    PrintableResponsePage,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    response_page_target,
    validate_printable_response_record_set,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_work_directory_destination,
    quillan_work_ref,
)

_ROUTE_ID = re.compile(r"^rt_[0-9a-f]{32}$")
_DETAIL_KEYS: Final[frozenset[str]] = frozenset(
    {"issuance_id", "logical_page", "total_pages"}
)


class PrintableResponseRouteError(ValueError):
    """Base error for Quillan-owned printable-response route operations."""


class PrintableResponseRouteValidationError(PrintableResponseRouteError):
    """Raised when a route plan is malformed or contradictory."""


class PrintableResponseRouteDestinationError(PrintableResponseRouteError):
    """Raised when a Core route destination is unsafe."""


class PrintableResponseRouteCollisionError(PrintableResponseRouteDestinationError):
    """Raised when an immutable Core route destination already exists."""

    def __init__(
        self,
        message: str,
        *,
        failed_page_id: str | None = None,
        current_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_page_id = failed_page_id
        self.current_path = current_path


class PrintableResponseRoutePersistenceError(PrintableResponseRouteError):
    """Raised when governed Core route persistence does not complete."""

    def __init__(
        self,
        message: str,
        *,
        created_paths: tuple[Path, ...] = (),
        verified_routes: tuple[RegisteredPrintableResponsePageRoute, ...] = (),
        failed_page_id: str | None = None,
        current_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.created_paths = created_paths
        self.verified_routes = verified_routes
        self.failed_page_id = failed_page_id
        self.current_path = current_path


class PrintableResponseRouteIntegrityError(PrintableResponseRoutePersistenceError):
    """Raised when durable records or routes contradict the plan."""


@dataclass(frozen=True, slots=True)
class PrintableResponsePageRoute:
    page: PrintableResponsePage
    locator: RouteLocator
    registration: RouteRegistration
    payload_text: str

    def __post_init__(self) -> None:
        _validate_page_route(self)


@dataclass(frozen=True, slots=True)
class RegisteredPrintableResponsePageRoute:
    route: PrintableResponsePageRoute
    registration_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.route, PrintableResponsePageRoute):
            raise PrintableResponseRouteValidationError(
                "route must be a PrintableResponsePageRoute."
            )
        _validate_page_route(self.route)
        if not isinstance(self.registration_path, Path):
            raise PrintableResponseRouteValidationError(
                "registration_path must be a Path."
            )

    @property
    def page(self) -> PrintableResponsePage:
        return self.route.page

    @property
    def locator(self) -> RouteLocator:
        return self.route.locator

    @property
    def registration(self) -> RouteRegistration:
        return self.route.registration

    @property
    def payload_text(self) -> str:
        return self.route.payload_text


@dataclass(frozen=True, slots=True)
class PersistedPrintableResponseRouteSet:
    record_set: PrintableResponseRecordSet
    routes: tuple[RegisteredPrintableResponsePageRoute, ...]

    def __post_init__(self) -> None:
        try:
            validate_printable_response_record_set(self.record_set)
        except PrintableResponseRecordValidationError as error:
            raise PrintableResponseRouteValidationError(str(error)) from error
        if not isinstance(self.routes, tuple) or not self.routes:
            raise PrintableResponseRouteValidationError(
                "routes must be a nonempty tuple."
            )
        if len(self.routes) != len(self.record_set.pages):
            raise PrintableResponseRouteValidationError(
                "Persisted route count must equal record-set page count."
            )
        for page, route in zip(self.record_set.pages, self.routes, strict=True):
            if not isinstance(route, RegisteredPrintableResponsePageRoute):
                raise PrintableResponseRouteValidationError(
                    "routes contains an invalid registered route."
                )
            if route.page != page:
                raise PrintableResponseRouteValidationError(
                    "Persisted routes contradict record-set order."
                )


def validate_route_id(value: object) -> str:
    if not isinstance(value, str) or _ROUTE_ID.fullmatch(value) is None:
        raise PrintableResponseRouteValidationError(
            "route_id must be rt_ followed by 32 lowercase hexadecimal characters."
        )
    return value


def printable_response_human_fallback(page: object) -> str:
    if not isinstance(page, PrintableResponsePage):
        raise PrintableResponseRouteValidationError(
            "page must be a PrintableResponsePage."
        )
    return (
        f"Quillan | class={page.class_id} | assignment={page.assignment_id} "
        f"| student={page.student_id} | page={page.logical_page}/"
        f"{page.total_pages} | page_id={page.page_id}"
    )


def printable_response_module_details(page: object) -> dict[str, int | str]:
    if not isinstance(page, PrintableResponsePage):
        raise PrintableResponseRouteValidationError(
            "page must be a PrintableResponsePage."
        )
    return {
        "issuance_id": page.issuance_id,
        "logical_page": page.logical_page,
        "total_pages": page.total_pages,
    }


def build_printable_response_page_route(
    page: object,
    route_id: object,
) -> PrintableResponsePageRoute:
    """Purely construct one exact Core route for an immutable page."""
    if not isinstance(page, PrintableResponsePage):
        raise PrintableResponseRouteValidationError(
            "page must be a PrintableResponsePage."
        )
    validated_route_id = validate_route_id(route_id)
    try:
        locator = RouteLocator(
            schema=PDS2_SCHEMA,
            work=ModuleWorkRef(
                module_id=QUILLAN_MODULE_ID,
                class_id=page.class_id,
                work_id=page.assignment_id,
            ),
            route_id=validated_route_id,
        )
        registration = RouteRegistration(
            schema_version=ROUTE_REGISTRATION_SCHEMA_VERSION,
            locator=locator,
            target=response_page_target(page),
            created_at=page.created_at,
            status="active",
            human_fallback=printable_response_human_fallback(page),
            module_details=printable_response_module_details(page),
        )
        payload = serialize_pds2_payload(locator)
        return PrintableResponsePageRoute(page, locator, registration, payload)
    except (RoutingModelError, Pds2PayloadError) as error:
        raise PrintableResponseRouteValidationError(str(error)) from error


def build_printable_response_route_set(
    record_set: object,
    route_ids: object,
) -> tuple[PrintableResponsePageRoute, ...]:
    """Build one ordered route for every page in a complete record set."""
    validated_record_set = _record_set(record_set)
    if not isinstance(route_ids, (tuple, list)):
        raise PrintableResponseRouteValidationError(
            "route_ids must be an ordered tuple or list."
        )
    ids = tuple(route_ids)
    if len(ids) != len(validated_record_set.pages):
        raise PrintableResponseRouteValidationError(
            "Route count must equal record-set page count."
        )
    routes = tuple(
        build_printable_response_page_route(page, route_id)
        for page, route_id in zip(validated_record_set.pages, ids, strict=True)
    )
    validate_printable_response_route_set(validated_record_set, routes)
    return routes


def validate_printable_response_route_set(
    record_set: object,
    routes: object,
) -> tuple[PrintableResponsePageRoute, ...]:
    validated_record_set = _record_set(record_set)
    if not isinstance(routes, tuple):
        raise PrintableResponseRouteValidationError("routes must be a tuple.")
    if len(routes) != len(validated_record_set.pages):
        raise PrintableResponseRouteValidationError(
            "Route count must equal record-set page count."
        )
    validated_routes: list[PrintableResponsePageRoute] = []
    for page, route in zip(validated_record_set.pages, routes, strict=True):
        if not isinstance(route, PrintableResponsePageRoute):
            raise PrintableResponseRouteValidationError(
                "Route set contains an invalid route."
            )
        _validate_page_route(route)
        if route.page != page:
            raise PrintableResponseRouteValidationError(
                "Route-set pages are reordered or contradictory."
            )
        validated_routes.append(route)
    for values, label in (
        ((route.locator.route_id for route in validated_routes), "route IDs"),
        ((route.locator for route in validated_routes), "locators"),
        ((route.registration.target for route in validated_routes), "targets"),
        ((route.page.page_id for route in validated_routes), "page IDs"),
    ):
        materialized = tuple(values)
        if len(set(materialized)) != len(materialized):
            raise PrintableResponseRouteValidationError(
                f"Route-set {label} must be unique."
            )
    return tuple(validated_routes)


def preflight_printable_response_route_collection(
    workspace_root: str | Path,
    work_ref: object,
) -> Path:
    """Validate every existing route-collection ancestor before discovery."""
    root = _workspace_root(workspace_root)
    validated_work = _work_ref(work_ref)
    try:
        return preflight_work_directory_destination(
            root, validated_work, "routes"
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseRouteDestinationError(str(error)) from error


def preflight_printable_response_route_destinations(
    workspace_root: str | Path,
    routes: object,
) -> tuple[Path, ...]:
    """Nonmutating preflight of complete Core-owned route destinations."""
    root = _workspace_root(workspace_root)
    if not isinstance(routes, (tuple, list)):
        raise PrintableResponseRouteDestinationError("routes must be ordered.")
    planned = tuple(routes)
    destinations: list[Path] = []
    for route in planned:
        if not isinstance(route, PrintableResponsePageRoute):
            raise PrintableResponseRouteDestinationError(
                "routes contains an invalid page route."
            )
        _validate_page_route(route)
        preflight_printable_response_route_collection(root, route.locator.work)
        path = route_registration_path(root, route.locator)
        _preflight_route_path(root, path, expect_existing_file=False)
        if os.path.lexists(path):
            raise PrintableResponseRouteCollisionError(
                f"Route registration already exists: {path}",
                failed_page_id=route.page.page_id,
                current_path=path,
            )
        destinations.append(path)
    if len(set(destinations)) != len(destinations):
        raise PrintableResponseRouteCollisionError(
            "Route registration destinations must be unique."
        )
    return tuple(destinations)


def validate_registered_printable_response_route_set(
    workspace_root: str | Path,
    work_ref: object,
    route_set: object,
) -> PersistedPrintableResponseRouteSet:
    """Reload and verify all records and routes in a governed persisted set."""
    root = _workspace_root(workspace_root)
    validated_work = _work_ref(work_ref)
    if not isinstance(route_set, PersistedPrintableResponseRouteSet):
        raise PrintableResponseRouteIntegrityError(
            "route_set must be a PersistedPrintableResponseRouteSet."
        )
    stored = _load_exact_record_set(root, validated_work, route_set.record_set)
    registered: list[RegisteredPrintableResponsePageRoute] = []
    for page, registered_route in zip(stored.pages, route_set.routes, strict=True):
        if registered_route.page != page:
            raise PrintableResponseRouteIntegrityError(
                "Registered route page contradicts persisted record order."
            )
        expected = route_registration_path(root, registered_route.locator)
        if registered_route.registration_path != expected:
            raise PrintableResponseRouteIntegrityError(
                "Registered route path is not canonical.",
                current_path=expected if os.path.lexists(expected) else None,
                failed_page_id=page.page_id,
            )
        _preflight_route_path(root, expected, expect_existing_file=True)
        try:
            loaded = load_route_registration(root, registered_route.locator)
        except (RouteRegistrationPersistenceError, RoutingModelError) as error:
            raise PrintableResponseRouteIntegrityError(
                f"Could not reload persisted route: {error}",
                current_path=expected if os.path.lexists(expected) else None,
                failed_page_id=page.page_id,
            ) from error
        if loaded != registered_route.registration:
            raise PrintableResponseRouteIntegrityError(
                "Persisted route registration does not equal its plan.",
                current_path=expected,
                failed_page_id=page.page_id,
            )
        registered.append(registered_route)
    return PersistedPrintableResponseRouteSet(stored, tuple(registered))


def persist_printable_response_route_set(
    workspace_root: str | Path,
    work_ref: object,
    persisted_record_set: object,
    routes: object,
) -> PersistedPrintableResponseRouteSet:
    """Persist and reload-verify routes for one exact durable prepared record set."""
    root = _workspace_root(workspace_root)
    validated_work = _work_ref(work_ref)
    if not isinstance(persisted_record_set, PersistedPrintableResponseRecordSet):
        raise PrintableResponseRouteValidationError(
            "persisted_record_set must be a PersistedPrintableResponseRecordSet."
        )
    planned_records = persisted_record_set.record_set
    stored = _load_exact_record_set(root, validated_work, planned_records)
    if stored.issuance.lifecycle.status != "prepared" or stored.issuance.lifecycle.revision != 1:
        raise PrintableResponseRouteIntegrityError(
            "Route persistence requires a prepared revision-1 issuance."
        )
    validated_routes = validate_printable_response_route_set(stored, routes)
    expected_paths = preflight_printable_response_route_destinations(
        root, validated_routes
    )
    registered: list[RegisteredPrintableResponsePageRoute] = []
    created_paths: list[Path] = []
    for route, expected in zip(validated_routes, expected_paths, strict=True):
        try:
            returned = write_route_registration(root, route.registration)
            if returned != expected:
                raise PrintableResponseRouteIntegrityError(
                    "Core returned a noncanonical route-registration path.",
                    created_paths=_proven_created_paths(
                        created_paths,
                        expected=expected,
                        write_succeeded=True,
                    ),
                    verified_routes=tuple(registered),
                    failed_page_id=route.page.page_id,
                    current_path=expected if os.path.lexists(expected) else None,
                )
            created_paths.append(returned)
            loaded = load_route_registration(root, route.locator)
            if loaded != route.registration:
                raise PrintableResponseRouteIntegrityError(
                    "Reloaded route registration does not exactly match its plan.",
                    created_paths=tuple(created_paths),
                    verified_routes=tuple(registered),
                    failed_page_id=route.page.page_id,
                    current_path=expected,
                )
            registered.append(RegisteredPrintableResponsePageRoute(route, returned))
        except PrintableResponseRoutePersistenceError:
            raise
        except (
            PrintableResponseRouteValidationError,
            RouteRegistrationPersistenceError,
            RoutingModelError,
            OSError,
        ) as error:
            current_path = expected if os.path.lexists(expected) else None
            collision = _is_exclusive_route_collision(error)
            raise PrintableResponseRoutePersistenceError(
                (
                    "Core exclusive route creation lost a collision for page "
                    if collision
                    else "Could not persist route for page "
                )
                + f"{route.page.page_id}: {error}",
                created_paths=_proven_created_paths(
                    created_paths,
                    expected=expected,
                    write_succeeded=False,
                ),
                verified_routes=tuple(registered),
                failed_page_id=route.page.page_id,
                current_path=current_path,
            ) from error
    return PersistedPrintableResponseRouteSet(stored, tuple(registered))


def _proven_created_paths(
    created: list[Path],
    *,
    expected: Path,
    write_succeeded: bool,
) -> tuple[Path, ...]:
    proven = [path for path in created if os.path.lexists(path)]
    if write_succeeded and os.path.lexists(expected) and expected not in proven:
        proven.append(expected)
    return tuple(proven)


def _is_exclusive_route_collision(error: BaseException) -> bool:
    return isinstance(error, RouteRegistrationWriteError) and isinstance(
        error.__cause__, FileExistsError
    )


def _record_set(value: object) -> PrintableResponseRecordSet:
    if not isinstance(value, PrintableResponseRecordSet):
        raise PrintableResponseRouteValidationError(
            "record_set must be a PrintableResponseRecordSet."
        )
    try:
        validate_printable_response_record_set(value)
    except PrintableResponseRecordValidationError as error:
        raise PrintableResponseRouteValidationError(str(error)) from error
    return value


def _work_ref(value: object) -> ModuleWorkRef:
    if not isinstance(value, ModuleWorkRef):
        raise PrintableResponseRouteValidationError(
            "work_ref must be a ModuleWorkRef."
        )
    try:
        expected = quillan_work_ref(value.class_id, value.work_id)
    except (RoutingModelError, ValueError, TypeError, AttributeError) as error:
        raise PrintableResponseRouteValidationError(str(error)) from error
    if value != expected:
        raise PrintableResponseRouteValidationError(
            f"work_ref.module_id must be {QUILLAN_MODULE_ID!r}."
        )
    return value


def _workspace_root(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise PrintableResponseRouteDestinationError(
            "workspace_root must be a string or Path."
        )
    supplied = Path(value)
    if not supplied.is_absolute():
        raise PrintableResponseRouteDestinationError(
            "workspace_root must be an absolute path."
        )
    return Path(os.path.abspath(supplied))


def _load_exact_record_set(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    planned: PrintableResponseRecordSet,
) -> PrintableResponseRecordSet:
    try:
        stored = load_printable_response_record_set(
            workspace_root, work_ref, planned.issuance.issuance_id
        )
    except PrintableResponsePersistenceError as error:
        raise PrintableResponseRouteIntegrityError(
            f"Could not load complete persisted response records: {error}"
        ) from error
    if stored != planned:
        raise PrintableResponseRouteIntegrityError(
            "Persisted response record set does not exactly equal its route plan."
        )
    return stored


def _validate_page_route(route: PrintableResponsePageRoute) -> None:
    if not isinstance(route.page, PrintableResponsePage):
        raise PrintableResponseRouteValidationError("route.page is invalid.")
    if not isinstance(route.locator, RouteLocator):
        raise PrintableResponseRouteValidationError("route.locator is invalid.")
    if not isinstance(route.registration, RouteRegistration):
        raise PrintableResponseRouteValidationError("route.registration is invalid.")
    if route.locator.schema != PDS2_SCHEMA:
        raise PrintableResponseRouteValidationError("Route locator schema is invalid.")
    validate_route_id(route.locator.route_id)
    expected_work = ModuleWorkRef(
        QUILLAN_MODULE_ID, route.page.class_id, route.page.assignment_id
    )
    if route.locator.work != expected_work:
        raise PrintableResponseRouteValidationError(
            "Route locator does not identify the exact Quillan work."
        )
    registration = route.registration
    if registration.schema_version != ROUTE_REGISTRATION_SCHEMA_VERSION:
        raise PrintableResponseRouteValidationError(
            "Registration schema version is invalid."
        )
    if registration.locator != route.locator:
        raise PrintableResponseRouteValidationError(
            "Registration locator does not equal route locator."
        )
    if registration.target != response_page_target(route.page):
        raise PrintableResponseRouteValidationError(
            "Registration target does not identify the exact page."
        )
    if registration.created_at != route.page.created_at:
        raise PrintableResponseRouteValidationError(
            "Registration timestamp does not equal page timestamp."
        )
    if registration.status != "active":
        raise PrintableResponseRouteValidationError("Registration must be active.")
    if registration.human_fallback != printable_response_human_fallback(route.page):
        raise PrintableResponseRouteValidationError(
            "Registration human_fallback contradicts the page."
        )
    details: Mapping[str, object] = registration.module_details
    if frozenset(details) != _DETAIL_KEYS or dict(details) != printable_response_module_details(route.page):
        raise PrintableResponseRouteValidationError(
            "Registration module_details contradict the page."
        )
    try:
        canonical = serialize_pds2_payload(route.locator)
        parsed = parse_pds2_payload(route.payload_text)
    except (Pds2PayloadError, RoutingModelError) as error:
        raise PrintableResponseRouteValidationError(str(error)) from error
    if route.payload_text != canonical:
        raise PrintableResponseRouteValidationError(
            "QR payload is not Core's canonical PDS2 serialization."
        )
    if parsed != route.locator:
        raise PrintableResponseRouteValidationError(
            "QR payload does not round-trip to the exact locator."
        )


def _preflight_route_path(root: Path, target: Path, *, expect_existing_file: bool) -> None:
    absolute_root = Path(os.path.abspath(root))
    absolute_target = Path(os.path.abspath(target))
    try:
        relative = absolute_target.relative_to(absolute_root)
    except ValueError as error:
        raise PrintableResponseRouteDestinationError(
            f"Route destination escapes workspace root: {target}"
        ) from error
    candidates = (
        absolute_root,
        *(
            absolute_root.joinpath(*relative.parts[:index])
            for index in range(1, len(relative.parts) + 1)
        ),
    )
    for index, candidate in enumerate(candidates):
        if not os.path.lexists(candidate):
            continue
        if _shared_is_link_like(candidate):
            raise PrintableResponseRouteDestinationError(
                f"Route path must not contain a symlink or junction: {candidate}"
            )
        is_target = index == len(candidates) - 1
        if is_target and expect_existing_file:
            if not candidate.is_file():
                raise PrintableResponseRouteDestinationError(
                    f"Route destination is not an ordinary file: {candidate}"
                )
        elif is_target:
            if not candidate.is_file():
                raise PrintableResponseRouteDestinationError(
                    f"Route destination has the wrong filesystem type: {candidate}"
                )
        elif not candidate.is_dir():
            raise PrintableResponseRouteDestinationError(
                f"Route ancestor is not a directory: {candidate}"
            )


__all__ = [
    "PersistedPrintableResponseRouteSet",
    "PrintableResponsePageRoute",
    "PrintableResponseRouteCollisionError",
    "PrintableResponseRouteDestinationError",
    "PrintableResponseRouteError",
    "PrintableResponseRouteIntegrityError",
    "PrintableResponseRoutePersistenceError",
    "PrintableResponseRouteValidationError",
    "RegisteredPrintableResponsePageRoute",
    "build_printable_response_page_route",
    "build_printable_response_route_set",
    "persist_printable_response_route_set",
    "preflight_printable_response_route_collection",
    "preflight_printable_response_route_destinations",
    "printable_response_human_fallback",
    "printable_response_module_details",
    "validate_printable_response_route_set",
    "validate_registered_printable_response_route_set",
    "validate_route_id",
]

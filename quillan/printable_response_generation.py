"""Managed transaction for PDS2 printable-response class packets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Final, cast

from pds_core.pds2 import Pds2PayloadError
from pds_core.route_ids import generate_route_id
from pds_core.route_registrations import (
    RouteRegistrationPersistenceError,
    load_route_registration,
)
from pds_core.routes import route_registration_path
from pds_core.rosters import StudentRecord, student_display_name
from pds_core.routing_models import PDS2_SCHEMA, ModuleWorkRef, RouteLocator, RoutingModelError

from quillan.printable_response import (
    PRINTABLE_RESPONSE_FILENAME,
    PrintableResponseRenderError,
    render_printable_response_pdf,
)
from quillan.assignments import AssignmentConfigError, validate_assignment_config
from quillan.printable_response_persistence import (
    PersistedPrintableResponseRecordSet,
    PrintableResponsePersistenceError,
    list_printable_response_issuances,
    load_printable_response_issuance,
    preflight_printable_response_record_sets,
    response_page_record_path,
    transition_printable_response_issuance,
    write_printable_response_record_set,
)
from quillan.printable_response_records import (
    PrintableResponseIssuance,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    build_printable_response_record_set,
    generate_artifact_id,
    generate_generation_id,
    generate_issuance_id,
    generate_page_id,
    validate_artifact_id,
    validate_generation_id,
    validate_printable_response_record_set,
)
from quillan.printable_response_routes import (
    PersistedPrintableResponseRouteSet,
    PrintableResponsePageRoute,
    PrintableResponseRouteError,
    PrintableResponseRoutePersistenceError,
    build_printable_response_route_set,
    persist_printable_response_route_set,
    preflight_printable_response_route_collection,
    preflight_printable_response_route_destinations,
    validate_printable_response_route_set,
    validate_route_id,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    initialize_managed_work_layout,
    preflight_managed_work_layout,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
)

MAX_ID_ATTEMPTS: Final[int] = 32
_SUPERSESSION_REASON: Final[str] = (
    "Replaced by successful Quillan printable-response regeneration."
)
_TEMPORARY_FILENAME = re.compile(
    r"^\.printable_response_pages\.[0-9a-f]{16}\.tmp\.pdf$"
)


class PrintableResponseGenerationError(RuntimeError):
    """Raised for a governed packet planning or validation failure."""


@dataclass(frozen=True, slots=True)
class PrintableResponseArtifactPlan:
    workspace_root: Path
    generation_id: str
    artifact_id: str
    work_ref: ModuleWorkRef
    assignment: Mapping[str, Any]
    students: tuple[StudentRecord, ...]
    record_sets: tuple[PrintableResponseRecordSet, ...]
    route_sets: tuple[tuple[PrintableResponsePageRoute, ...], ...]
    predecessors: tuple[PrintableResponseIssuance | None, ...]
    output_path: Path
    temporary_path: Path
    replacing_existing: bool
    assignment_title: str
    pages_per_student: int
    output_relative_path: str
    expected_output_digest: str | None


@dataclass(frozen=True, slots=True)
class GeneratedPrintableResponsePacket:
    class_id: str
    assignment_id: str
    assignment_title: str
    generation_id: str
    artifact_id: str
    output_path: Path
    output_relative_path: str
    success: bool
    installed: bool
    replaced_existing: bool
    student_count: int
    issuance_count: int
    physical_page_count: int
    pages_per_student: int
    issuance_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    planned_route_count: int
    created_route_count: int
    verified_route_count: int
    predecessor_count: int
    superseded_predecessor_count: int
    failure_stage: str | None
    error: str | None
    warnings: tuple[str, ...]
    created_registration_paths: tuple[Path, ...]
    verified_registration_paths: tuple[Path, ...]
    failed_predecessor_ids: tuple[str, ...]

    @property
    def total_page_count(self) -> int:
        return self.physical_page_count

    @property
    def partial_success(self) -> bool:
        return self.installed and not self.success


@dataclass(frozen=True, slots=True)
class IdentityGenerators:
    generation: Callable[[], str] = generate_generation_id
    artifact: Callable[[], str] = generate_artifact_id
    issuance: Callable[[], str] = generate_issuance_id
    page: Callable[[], str] = generate_page_id
    route: Callable[[], str] = generate_route_id


@dataclass(frozen=True, slots=True)
class _OwnedTemporaryFile:
    path: Path
    device: int
    inode: int


def select_printable_response_predecessors(
    workspace_root: str | Path,
    work_ref: object,
    students: object,
) -> tuple[PrintableResponseIssuance | None, ...]:
    """Strictly select zero or one current issued predecessor per roster student."""
    root = _absolute_workspace_root(workspace_root)
    validated_work = _validated_work_ref(work_ref)
    if not isinstance(students, tuple) or not all(
        isinstance(student, StudentRecord) for student in students
    ):
        raise PrintableResponseGenerationError(
            "students must be a tuple of StudentRecord values."
        )
    try:
        historical = list_printable_response_issuances(
            root, validated_work
        )
    except PrintableResponsePersistenceError as error:
        raise PrintableResponseGenerationError(
            f"Could not inspect printable-response issuance history: {error}"
        ) from error
    selected: list[PrintableResponseIssuance | None] = []
    for student in students:
        matching = tuple(
            issuance
            for issuance in historical
            if (
                issuance.class_id,
                issuance.assignment_id,
                issuance.student_id,
                issuance.generation_context.output_kind,
            )
            == (
                validated_work.class_id,
                validated_work.work_id,
                student.student_id,
                "class_packet_pdf",
            )
            and issuance.lifecycle.status not in {
                "cancelled",
                "superseded",
                "invalidated",
            }
        )
        if any(item.lifecycle.status == "prepared" for item in matching):
            raise PrintableResponseGenerationError(
                f"Prepared predecessor blocks generation for student {student.student_id}."
            )
        issued = tuple(item for item in matching if item.lifecycle.status == "issued")
        if len(issued) > 1:
            raise PrintableResponseGenerationError(
                f"Issued predecessor lineage is ambiguous for student {student.student_id}."
            )
        selected.append(issued[0] if issued else None)
    return tuple(selected)


def build_printable_response_artifact_plan(
    *,
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    assignment: Mapping[str, Any],
    students: tuple[StudentRecord, ...],
    pages_per_student: int,
    output_path: Path,
    predecessors: tuple[PrintableResponseIssuance | None, ...],
    generators: IdentityGenerators = IdentityGenerators(),
    clock: Callable[[], datetime | str] | None = None,
    max_attempts: int = MAX_ID_ATTEMPTS,
) -> PrintableResponseArtifactPlan:
    """Allocate and strictly validate a complete nonmutating artifact plan."""
    root = _absolute_workspace_root(workspace_root)
    validated_work = _validated_work_ref(work_ref)
    validated_assignment = _validated_assignment_mapping(assignment, validated_work)
    canonical_output, replacing_existing = _canonical_output(
        root, validated_work, output_path
    )
    if not isinstance(students, tuple) or not students:
        raise PrintableResponseGenerationError(
            "students must be a nonempty tuple."
        )
    if not all(isinstance(student, StudentRecord) for student in students):
        raise PrintableResponseGenerationError(
            "students must contain only StudentRecord values."
        )
    if not isinstance(predecessors, tuple) or len(predecessors) != len(students):
        raise PrintableResponseGenerationError(
            "predecessors must align exactly with students."
        )
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise PrintableResponseGenerationError("max_attempts must be positive.")
    try:
        historical = list_printable_response_issuances(root, validated_work)
        existing_route_ids, existing_route_target_ids = _existing_route_identities(
            root, validated_work
        )
    except (PrintableResponsePersistenceError, PrintableResponseRouteError) as error:
        raise PrintableResponseGenerationError(str(error)) from error
    allocated_ids: set[str] = set(existing_route_ids)
    allocated_ids.update(existing_route_target_ids)
    for issuance in historical:
        allocated_ids.update(
            {
                issuance.generation_id,
                issuance.artifact_id,
                issuance.issuance_id,
                *issuance.page_ids,
            }
        )
    generation_id = _fresh(
        generators.generation, allocated_ids, max_attempts, "generation"
    )
    artifact_id = _fresh(
        generators.artifact, allocated_ids, max_attempts, "artifact"
    )
    planned_record_sets: list[PrintableResponseRecordSet] = []
    planned_route_sets: list[tuple[PrintableResponsePageRoute, ...]] = []
    try:
        for student, predecessor in zip(students, predecessors, strict=True):
            issuance_id = _fresh(
                generators.issuance, allocated_ids, max_attempts, "issuance"
            )
            page_ids = tuple(
                _fresh_page_destination(
                    root,
                    validated_work,
                    generators.page,
                    allocated_ids,
                    max_attempts,
                )
                for _ in range(pages_per_student)
            )
            records = build_printable_response_record_set(
                validated_work.class_id,
                validated_assignment,
                student,
                generation_id=generation_id,
                artifact_id=artifact_id,
                output_kind="class_packet_pdf",
                reason="regeneration" if predecessor is not None else "initial",
                predecessor_issuance_id=(
                    predecessor.issuance_id if predecessor is not None else None
                ),
                pages_per_student=pages_per_student,
                issuance_id=issuance_id,
                page_ids=page_ids,
                class_label=validated_work.class_id,
                clock=clock,
            )
            planned_route_ids = tuple(
                _fresh_route_destination(
                    root,
                    records,
                    generators.route,
                    allocated_ids,
                    max_attempts,
                )
                for _page in records.pages
            )
            planned_record_sets.append(records)
            planned_route_sets.append(
                build_printable_response_route_set(records, planned_route_ids)
            )
        preflight_printable_response_record_sets(
            root, validated_work, tuple(planned_record_sets)
        )
        preflight_printable_response_route_destinations(
            root,
            tuple(route for routes in planned_route_sets for route in routes),
        )
        paths = quillan_work_paths(
            root, validated_work.class_id, validated_work.work_id
        )
        preflight_managed_work_layout(paths)
    except (
        PrintableResponsePersistenceError,
        PrintableResponseRecordValidationError,
        PrintableResponseRouteError,
        QuillanWorkPathError,
        OSError,
        ValueError,
    ) as error:
        raise PrintableResponseGenerationError(str(error)) from error
    temporary = paths.templates_dir / (
        f".{Path(PRINTABLE_RESPONSE_FILENAME).stem}.{secrets.token_hex(8)}.tmp.pdf"
    )
    try:
        preflight_work_file_destination(
            root, validated_work, Path("templates") / temporary.name
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseGenerationError(str(error)) from error
    artifact = PrintableResponseArtifactPlan(
        root,
        generation_id,
        artifact_id,
        validated_work,
        validated_assignment,
        students,
        tuple(planned_record_sets),
        tuple(planned_route_sets),
        predecessors,
        canonical_output,
        temporary,
        replacing_existing,
        str(validated_assignment["title"]),
        pages_per_student,
        canonical_output.relative_to(root).as_posix(),
        sha256_file(canonical_output) if replacing_existing else None,
    )
    return validate_printable_response_artifact_plan(artifact)


def validate_printable_response_artifact_plan(
    value: object,
) -> PrintableResponseArtifactPlan:
    """Strictly revalidate all plan authority without filesystem mutation."""
    if not isinstance(value, PrintableResponseArtifactPlan):
        raise PrintableResponseGenerationError(
            "artifact must be a PrintableResponseArtifactPlan."
        )
    root = _absolute_workspace_root(value.workspace_root)
    work_ref = _validated_work_ref(value.work_ref)
    canonical_output, current_exists = _canonical_output(
        root, work_ref, value.output_path
    )
    if value.output_path != canonical_output:
        raise PrintableResponseGenerationError("Artifact output path is not canonical.")
    if not isinstance(value.replacing_existing, bool):
        raise PrintableResponseGenerationError("replacing_existing must be a boolean.")
    if value.replacing_existing != current_exists:
        raise PrintableResponseGenerationError(
            "Canonical output existence changed before artifact execution."
        )
    if not isinstance(value.temporary_path, Path) or not value.temporary_path.is_absolute():
        raise PrintableResponseGenerationError(
            "Artifact temporary path must be an absolute Path."
        )
    temporary = Path(os.path.abspath(value.temporary_path))
    paths = quillan_work_paths(root, work_ref.class_id, work_ref.work_id)
    if (
        temporary != value.temporary_path
        or temporary.parent != paths.templates_dir
        or _TEMPORARY_FILENAME.fullmatch(temporary.name) is None
    ):
        raise PrintableResponseGenerationError(
            "Artifact temporary path must be an immediate governed templates child."
        )
    try:
        preflight_managed_work_layout(paths)
        checked_temporary = preflight_work_file_destination(
            root, work_ref, Path("templates") / temporary.name
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseGenerationError(str(error)) from error
    if checked_temporary != temporary:
        raise PrintableResponseGenerationError("Artifact temporary path is not canonical.")
    try:
        validate_generation_id(value.generation_id)
        validate_artifact_id(value.artifact_id)
    except PrintableResponseRecordValidationError as error:
        raise PrintableResponseGenerationError(str(error)) from error
    assignment = _validated_assignment_mapping(value.assignment, work_ref)
    if value.assignment_title != assignment["title"]:
        raise PrintableResponseGenerationError(
            "Artifact assignment_title contradicts its assignment."
        )
    if (
        isinstance(value.pages_per_student, bool)
        or not isinstance(value.pages_per_student, int)
        or value.pages_per_student < 1
    ):
        raise PrintableResponseGenerationError(
            "Artifact pages_per_student must be a positive integer."
        )
    expected_relative = canonical_output.relative_to(root).as_posix()
    if value.output_relative_path != expected_relative:
        raise PrintableResponseGenerationError(
            "Artifact output_relative_path is not canonical."
        )
    if value.replacing_existing:
        if (
            not isinstance(value.expected_output_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", value.expected_output_digest) is None
            or sha256_file(canonical_output) != value.expected_output_digest
        ):
            raise PrintableResponseGenerationError(
                "Artifact expected_output_digest is invalid or stale."
            )
    elif value.expected_output_digest is not None:
        raise PrintableResponseGenerationError(
            "A non-replacement artifact must not have an output digest."
        )
    if not isinstance(value.students, tuple) or not value.students:
        raise PrintableResponseGenerationError("artifact.students must be nonempty.")
    if not all(isinstance(student, StudentRecord) for student in value.students):
        raise PrintableResponseGenerationError(
            "artifact.students contains a wrong model type."
        )
    if (
        not isinstance(value.record_sets, tuple)
        or len(value.record_sets) != len(value.students)
        or not isinstance(value.route_sets, tuple)
        or len(value.route_sets) != len(value.record_sets)
        or not isinstance(value.predecessors, tuple)
        or len(value.predecessors) != len(value.students)
    ):
        raise PrintableResponseGenerationError(
            "Artifact students, records, routes, and predecessors must align."
        )
    seen_page_ids: set[str] = set()
    seen_route_ids: set[str] = set()
    physical_page_count = 0
    for student, record_set, routes, predecessor in zip(
        value.students,
        value.record_sets,
        value.route_sets,
        value.predecessors,
        strict=True,
    ):
        if not isinstance(record_set, PrintableResponseRecordSet):
            raise PrintableResponseGenerationError(
                "artifact.record_sets contains a wrong model type."
            )
        try:
            validate_printable_response_record_set(record_set)
            validate_printable_response_route_set(record_set, routes)
        except (
            PrintableResponseRecordValidationError,
            PrintableResponseRouteError,
        ) as error:
            raise PrintableResponseGenerationError(str(error)) from error
        issuance = record_set.issuance
        if (
            issuance.generation_id != value.generation_id
            or issuance.artifact_id != value.artifact_id
            or issuance.class_id != work_ref.class_id
            or issuance.assignment_id != work_ref.work_id
            or issuance.student_id != student.student_id
        ):
            raise PrintableResponseGenerationError(
                "Artifact record provenance contradicts the plan."
            )
        snapshot = issuance.assignment_snapshot
        if (
            snapshot.schema_version != assignment["schema_version"]
            or snapshot.title != assignment["title"]
            or snapshot.updated_at != assignment["updated_at"]
        ):
            raise PrintableResponseGenerationError(
                "Issuance assignment snapshot contradicts the artifact assignment."
            )
        student_snapshot = issuance.student_snapshot
        if (
            issuance.student_id != student.student_id
            or student_snapshot.display_name != student_display_name(student)
            or student_snapshot.last_name != student.last_name
            or student_snapshot.first_name != student.first_name
            or student_snapshot.period != student.period
        ):
            raise PrintableResponseGenerationError(
                "Issuance student snapshot contradicts its roster student."
            )
        if (
            issuance.page_count != value.pages_per_student
            or len(record_set.pages) != value.pages_per_student
            or len(routes) != value.pages_per_student
        ):
            raise PrintableResponseGenerationError(
                "Artifact page counts must be positive and homogeneous."
            )
        physical_page_count += len(record_set.pages)
        if predecessor is not None and not isinstance(predecessor, PrintableResponseIssuance):
            raise PrintableResponseGenerationError(
                "artifact.predecessors contains a wrong model type."
            )
        context = issuance.generation_context
        if predecessor is None:
            if context.reason != "initial" or context.predecessor_issuance_id is not None:
                raise PrintableResponseGenerationError(
                    "Initial issuance predecessor semantics are invalid."
                )
        else:
            try:
                stored_predecessor = load_printable_response_issuance(
                    root, work_ref, predecessor.issuance_id
                )
            except PrintableResponsePersistenceError as error:
                raise PrintableResponseGenerationError(
                    f"Could not validate predecessor issuance: {error}"
                ) from error
            if stored_predecessor != predecessor:
                raise PrintableResponseGenerationError(
                    "Artifact predecessor does not equal canonical persistence."
                )
            if (
                predecessor.lifecycle.status != "issued"
                or predecessor.class_id != work_ref.class_id
                or predecessor.assignment_id != work_ref.work_id
                or predecessor.student_id != student.student_id
                or predecessor.generation_context.output_kind != "class_packet_pdf"
                or context.reason != "regeneration"
                or context.predecessor_issuance_id != predecessor.issuance_id
            ):
                raise PrintableResponseGenerationError(
                    "Artifact predecessor semantics are invalid."
                )
        current_page_ids = {page.page_id for page in record_set.pages}
        current_route_ids = {route.locator.route_id for route in routes}
        if seen_page_ids.intersection(current_page_ids) or seen_route_ids.intersection(
            current_route_ids
        ):
            raise PrintableResponseGenerationError(
                "Artifact page and route identities must be unique."
            )
        seen_page_ids.update(current_page_ids)
        seen_route_ids.update(current_route_ids)
    if physical_page_count != len(value.students) * value.pages_per_student:
        raise PrintableResponseGenerationError(
            "Artifact total physical page count is inconsistent."
        )
    return value


def execute_printable_response_artifact(
    artifact: object,
    *,
    output_relative_path: str,
    expected_output_digest: str | None,
    overwrite: bool,
    clock: Callable[[], datetime | str] | None = None,
) -> GeneratedPrintableResponsePacket:
    """Execute the governed records/routes/render/install/supersede transaction."""
    validated = validate_printable_response_artifact_plan(artifact)
    if output_relative_path != validated.output_relative_path:
        raise PrintableResponseGenerationError(
            "output_relative_path does not identify the canonical artifact output."
        )
    if not isinstance(overwrite, bool):
        raise PrintableResponseGenerationError("overwrite must be a boolean.")
    if validated.replacing_existing:
        if (
            not overwrite
            or expected_output_digest != validated.expected_output_digest
            or not isinstance(expected_output_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_output_digest) is None
        ):
            raise PrintableResponseGenerationError(
                "Replacing a planned output requires overwrite and its digest."
            )
    elif expected_output_digest is not None:
        raise PrintableResponseGenerationError(
            "A non-replacement artifact cannot carry an output digest."
        )
    workspace_root = validated.workspace_root
    persisted: list[PersistedPrintableResponseRecordSet] = []
    persisted_routes: list[PersistedPrintableResponseRouteSet] = []
    created_paths: list[Path] = []
    verified_paths: list[Path] = []
    warnings: list[str] = []
    stage = "preflight"
    primary_error: str | None = None
    installed = False
    superseded = 0
    failed_predecessors: list[str] = []
    owned_temporary: _OwnedTemporaryFile | None = None
    planned_route_paths = tuple(
        route_registration_path(workspace_root, route.locator)
        for route_set in validated.route_sets
        for route in route_set
    )
    try:
        preflight_printable_response_record_sets(
            workspace_root, validated.work_ref, validated.record_sets
        )
        preflight_printable_response_route_destinations(
            workspace_root,
            tuple(route for routes in validated.route_sets for route in routes),
        )
        initialize_managed_work_layout(
            quillan_work_paths(
                workspace_root,
                validated.work_ref.class_id,
                validated.work_ref.work_id,
            )
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                validated.temporary_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            metadata = os.fstat(descriptor)
            owned_temporary = _OwnedTemporaryFile(
                validated.temporary_path,
                metadata.st_dev,
                metadata.st_ino,
            )
        finally:
            if descriptor is not None:
                os.close(descriptor)
        stage = "record_persistence"
        for record_set in validated.record_sets:
            persisted.append(
                write_printable_response_record_set(
                    workspace_root, validated.work_ref, record_set
                )
            )
        stage = "route_persistence"
        for persisted_record_set, planned_routes in zip(
            persisted, validated.route_sets, strict=True
        ):
            try:
                route_result = persist_printable_response_route_set(
                    workspace_root,
                    validated.work_ref,
                    persisted_record_set,
                    planned_routes,
                )
            except PrintableResponseRoutePersistenceError as error:
                created_paths.extend(
                    path for path in error.created_paths if path not in created_paths
                )
                for route in error.verified_routes:
                    if route.registration_path not in verified_paths:
                        verified_paths.append(route.registration_path)
                raise
            persisted_routes.append(route_result)
            created_paths.extend(
                route.registration_path for route in route_result.routes
            )
            verified_paths.extend(
                route.registration_path for route in route_result.routes
            )
        stage = "pdf_rendering"
        _require_owned_temporary(owned_temporary, "rendering")
        render_printable_response_pdf(
            workspace_root,
            validated.work_ref,
            validated.temporary_path,
            tuple(zip(persisted, persisted_routes, strict=True)),
        )
        _require_owned_temporary(owned_temporary, "completed PDF validation")
        _validate_temporary_pdf(validated.temporary_path)
        stage = "issuance_finalization"
        issued_at = _now(clock)
        for record_set in validated.record_sets:
            transition_printable_response_issuance(
                workspace_root,
                validated.work_ref,
                record_set.issuance.issuance_id,
                expected_revision=1,
                new_status="issued",
                timestamp=issued_at,
            )
        stage = "pdf_installation"
        _check_concurrent_output(
            validated.output_path, expected_output_digest, overwrite
        )
        _require_owned_temporary(owned_temporary, "installation")
        os.replace(validated.temporary_path, validated.output_path)
        owned_temporary = None
        installed = True
        stage = "predecessor_supersession"
        superseded_at = _now(clock)
        for predecessor, replacement in zip(
            validated.predecessors, validated.record_sets, strict=True
        ):
            if predecessor is None:
                continue
            try:
                transition_printable_response_issuance(
                    workspace_root,
                    validated.work_ref,
                    predecessor.issuance_id,
                    expected_revision=predecessor.lifecycle.revision,
                    new_status="superseded",
                    timestamp=superseded_at,
                    reason=_SUPERSESSION_REASON,
                    replacement_issuance_id=replacement.issuance.issuance_id,
                )
                superseded += 1
            except (PrintableResponsePersistenceError, OSError) as error:
                failed_predecessors.append(predecessor.issuance_id)
                warnings.append(
                    "Predecessor supersession failed for issuance "
                    f"{predecessor.issuance_id}: {error}"
                )
        if failed_predecessors:
            primary_error = (
                "Packet was installed, but predecessor lineage requires resolution."
            )
    except (
        PrintableResponseGenerationError,
        PrintableResponsePersistenceError,
        PrintableResponseRenderError,
        PrintableResponseRouteError,
        QuillanWorkPathError,
        OSError,
    ) as error:
        primary_error = str(error)
        present_planned_routes = (
            tuple(path for path in planned_route_paths if os.path.lexists(path))
            if stage == "route_persistence"
            else ()
        )
        competing_paths = tuple(
            path for path in present_planned_routes if path not in created_paths
        )
        warnings.extend(
            "Planned route destination exists but was not reported as created by "
            f"this operation: {path}"
            for path in competing_paths
        )
        route_may_exist = bool(present_planned_routes) or any(
            os.path.lexists(path) for path in created_paths
        )
        terminal = (
            "invalidated"
            if route_may_exist
            or stage
            in {"pdf_rendering", "issuance_finalization", "pdf_installation"}
            else "cancelled"
        )
        _compensate_issuances(
            workspace_root,
            validated.work_ref,
            persisted,
            transition=terminal,
            primary_stage=stage,
            clock=clock,
            warnings=warnings,
        )
    finally:
        if owned_temporary is not None:
            cleanup_warning = _cleanup_owned_temporary(owned_temporary, stage)
            if cleanup_warning is not None:
                warnings.append(cleanup_warning)
    clean = installed and not failed_predecessors and primary_error is None
    return _result(
        validated,
        success=clean,
        installed=installed,
        superseded=superseded,
        failure_stage=None if clean else stage,
        error=primary_error,
        warnings=tuple(warnings),
        created_paths=tuple(created_paths),
        verified_paths=tuple(verified_paths),
        failed_predecessors=tuple(failed_predecessors),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_workspace_root(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise PrintableResponseGenerationError(
            "workspace_root must be a string or Path."
        )
    supplied = Path(value)
    if not supplied.is_absolute():
        raise PrintableResponseGenerationError(
            "workspace_root must be an absolute path."
        )
    return Path(os.path.abspath(supplied))


def _matches_owned_temporary(owned: _OwnedTemporaryFile) -> bool:
    try:
        if _is_link_like(owned.path):
            return False
        metadata = os.lstat(owned.path)
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_dev == owned.device
        and metadata.st_ino == owned.inode
    )


def _require_owned_temporary(
    owned: _OwnedTemporaryFile | None, action: str
) -> None:
    if owned is None or not _matches_owned_temporary(owned):
        raise PrintableResponseGenerationError(
            f"Temporary-file ownership was lost before {action}."
        )


def _cleanup_owned_temporary(
    owned: _OwnedTemporaryFile, primary_stage: str
) -> str | None:
    if not os.path.lexists(owned.path):
        return None
    if not _matches_owned_temporary(owned):
        return (
            "Temporary cleanup preserved an entry no longer owned by this operation "
            f"after primary stage {primary_stage}: {owned.path}"
        )
    try:
        owned.path.unlink()
    except OSError as error:
        return (
            f"Temporary cleanup failed after primary stage {primary_stage} "
            f"for {owned.path}: {error}"
        )
    return None


def _validated_work_ref(value: object) -> ModuleWorkRef:
    if not isinstance(value, ModuleWorkRef):
        raise PrintableResponseGenerationError(
            "work_ref must be a ModuleWorkRef."
        )
    try:
        expected = quillan_work_ref(value.class_id, value.work_id)
    except (RoutingModelError, ValueError, TypeError, AttributeError) as error:
        raise PrintableResponseGenerationError(str(error)) from error
    if value != expected:
        raise PrintableResponseGenerationError(
            "work_ref must identify exact Quillan work."
        )
    return value


def _validated_assignment_mapping(
    value: object, work_ref: ModuleWorkRef
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PrintableResponseGenerationError(
            "artifact.assignment must be a mapping."
        )
    assignment = cast(dict[str, Any], dict(value))
    try:
        validate_assignment_config(assignment)
    except (AssignmentConfigError, TypeError, ValueError) as error:
        raise PrintableResponseGenerationError(
            f"artifact.assignment is invalid: {error}"
        ) from error
    if assignment["assignment_id"] != work_ref.work_id:
        raise PrintableResponseGenerationError(
            "Artifact assignment_id contradicts work_ref."
        )
    if work_ref.class_id not in assignment["class_ids"]:
        raise PrintableResponseGenerationError(
            "Artifact assignment does not include work_ref.class_id."
        )
    return assignment


def _canonical_output(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    supplied: object,
) -> tuple[Path, bool]:
    if not isinstance(supplied, Path) or not supplied.is_absolute():
        raise PrintableResponseGenerationError(
            "output_path must be an absolute Path."
        )
    output = Path(os.path.abspath(supplied))
    paths = quillan_work_paths(
        workspace_root, work_ref.class_id, work_ref.work_id
    )
    expected = paths.templates_dir / PRINTABLE_RESPONSE_FILENAME
    if output != expected or supplied != output or output.name != PRINTABLE_RESPONSE_FILENAME:
        raise PrintableResponseGenerationError(
            "output_path must equal the exact canonical printable-response PDF path."
        )
    try:
        checked = preflight_work_file_destination(
            workspace_root,
            work_ref,
            Path("templates") / PRINTABLE_RESPONSE_FILENAME,
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseGenerationError(str(error)) from error
    if checked != output:
        raise PrintableResponseGenerationError("Canonical output containment failed.")
    exists = os.path.lexists(output)
    if exists and (_is_link_like(output) or not output.is_file()):
        raise PrintableResponseGenerationError(
            "Canonical output must be an ordinary non-link file."
        )
    return output, exists


def _fresh(
    generator: Callable[[], str],
    allocated: set[str],
    max_attempts: int,
    label: str,
) -> str:
    for _ in range(max_attempts):
        value = generator()
        if value in allocated:
            continue
        allocated.add(value)
        return value
    raise PrintableResponseGenerationError(
        f"Could not allocate a fresh {label} identity after {max_attempts} attempts."
    )


def _fresh_route_destination(
    workspace_root: Path,
    records: PrintableResponseRecordSet,
    generator: Callable[[], str],
    allocated: set[str],
    max_attempts: int,
) -> str:
    for _ in range(max_attempts):
        value = generator()
        try:
            validate_route_id(value)
        except PrintableResponseRouteError as error:
            raise PrintableResponseGenerationError(str(error)) from error
        if value in allocated:
            continue
        allocated.add(value)
        path = route_registration_path(workspace_root, _locator(records, value))
        if not os.path.lexists(path):
            return value
    raise PrintableResponseGenerationError(
        f"Could not allocate a fresh route identity after {max_attempts} attempts."
    )


def _fresh_page_destination(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    generator: Callable[[], str],
    allocated: set[str],
    max_attempts: int,
) -> str:
    for _ in range(max_attempts):
        value = generator()
        if value in allocated:
            continue
        allocated.add(value)
        try:
            path = response_page_record_path(workspace_root, work_ref, value)
        except (PrintableResponseRecordValidationError, QuillanWorkPathError) as error:
            raise PrintableResponseGenerationError(str(error)) from error
        if not os.path.lexists(path):
            return value
    raise PrintableResponseGenerationError(
        f"Could not allocate a fresh page identity after {max_attempts} attempts."
    )


def _existing_route_identities(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
) -> tuple[set[str], set[str]]:
    try:
        directory = preflight_printable_response_route_collection(
            workspace_root, work_ref
        )
    except PrintableResponseRouteError as error:
        raise PrintableResponseGenerationError(str(error)) from error
    if not os.path.lexists(directory):
        return set(), set()
    existing_route_ids: set[str] = set()
    existing_route_target_ids: set[str] = set()
    try:
        children = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    except OSError as error:
        raise PrintableResponseGenerationError(
            f"Could not inspect Core route collection: {error}"
        ) from error
    for child in children:
        if _is_link_like(child) or not child.is_file() or child.suffix != ".json":
            raise PrintableResponseGenerationError(
                f"Core route collection contains an invalid direct child: {child}"
            )
        try:
            route_id = validate_route_id(child.stem)
            locator = RouteLocator(PDS2_SCHEMA, work_ref, route_id)
            registration = load_route_registration(workspace_root, locator)
        except (
            PrintableResponseRouteError,
            RouteRegistrationPersistenceError,
            RoutingModelError,
            Pds2PayloadError,
        ) as error:
            raise PrintableResponseGenerationError(
                f"Invalid existing Core route registration {child}: {error}"
            ) from error
        existing_route_ids.add(route_id)
        existing_route_target_ids.add(registration.target.record_id)
    return existing_route_ids, existing_route_target_ids


def _locator(records: PrintableResponseRecordSet, route_id: str) -> RouteLocator:
    issuance = records.issuance
    return RouteLocator(
        PDS2_SCHEMA,
        ModuleWorkRef("quillan", issuance.class_id, issuance.assignment_id),
        route_id,
    )


def _now(clock: Callable[[], datetime | str] | None) -> str:
    value = datetime.now(timezone.utc) if clock is None else clock()
    return value.isoformat() if isinstance(value, datetime) else value


def _validate_temporary_pdf(path: Path) -> None:
    if (
        not os.path.lexists(path)
        or _is_link_like(path)
        or not path.is_file()
        or path.stat().st_size == 0
        or not path.read_bytes().startswith(b"%PDF")
    ):
        raise PrintableResponseGenerationError(
            "Temporary output is not a nonempty ordinary PDF file."
        )
    with path.open("r+b") as file:
        os.fsync(file.fileno())


def _check_concurrent_output(
    path: Path, expected_digest: str | None, overwrite: bool
) -> None:
    if not overwrite or expected_digest is None:
        if os.path.lexists(path):
            raise PrintableResponseGenerationError(
                "Canonical output changed concurrently before installation."
            )
        return
    if not os.path.lexists(path):
        raise PrintableResponseGenerationError(
            "Canonical output disappeared concurrently before installation."
        )
    if _is_link_like(path) or not path.is_file():
        raise PrintableResponseGenerationError(
            "Canonical output changed filesystem type before installation."
        )
    if sha256_file(path) != expected_digest:
        raise PrintableResponseGenerationError(
            "Canonical output content changed concurrently before installation."
        )


def _compensate_issuances(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    persisted: list[PersistedPrintableResponseRecordSet],
    *,
    transition: str,
    primary_stage: str,
    clock: Callable[[], datetime | str] | None,
    warnings: list[str],
) -> None:
    for persisted_set in persisted:
        issuance_id = persisted_set.record_set.issuance.issuance_id
        try:
            current = load_printable_response_issuance(
                workspace_root, work_ref, issuance_id
            )
            if current.lifecycle.status not in {"prepared", "issued"}:
                continue
            transition_printable_response_issuance(
                workspace_root,
                work_ref,
                issuance_id,
                expected_revision=current.lifecycle.revision,
                new_status=transition,
                timestamp=_now(clock),
                reason=f"Printable-response generation failed during {primary_stage}.",
            )
        except (PrintableResponsePersistenceError, OSError) as error:
            warnings.append(
                f"Compensation failed for issuance {issuance_id}; attempted "
                f"{transition} after primary stage {primary_stage}: {error}"
            )


def _result(
    artifact: PrintableResponseArtifactPlan,
    *,
    success: bool,
    installed: bool,
    superseded: int,
    failure_stage: str | None,
    error: str | None,
    warnings: tuple[str, ...],
    created_paths: tuple[Path, ...],
    verified_paths: tuple[Path, ...],
    failed_predecessors: tuple[str, ...],
) -> GeneratedPrintableResponsePacket:
    issuance_ids = tuple(item.issuance.issuance_id for item in artifact.record_sets)
    page_ids = tuple(
        page.page_id for item in artifact.record_sets for page in item.pages
    )
    result_route_ids = tuple(
        route.locator.route_id for routes in artifact.route_sets for route in routes
    )
    return GeneratedPrintableResponsePacket(
        artifact.work_ref.class_id,
        artifact.work_ref.work_id,
        artifact.assignment_title,
        artifact.generation_id,
        artifact.artifact_id,
        artifact.output_path,
        artifact.output_relative_path,
        success,
        installed,
        artifact.replacing_existing and installed,
        len(artifact.students),
        len(issuance_ids),
        len(page_ids),
        artifact.pages_per_student,
        issuance_ids,
        page_ids,
        result_route_ids,
        len(result_route_ids),
        len(created_paths),
        len(verified_paths),
        sum(item is not None for item in artifact.predecessors),
        superseded,
        failure_stage,
        error,
        warnings,
        created_paths,
        verified_paths,
        failed_predecessors,
    )


__all__ = [
    "GeneratedPrintableResponsePacket",
    "IdentityGenerators",
    "PrintableResponseArtifactPlan",
    "PrintableResponseGenerationError",
    "build_printable_response_artifact_plan",
    "execute_printable_response_artifact",
    "select_printable_response_predecessors",
    "sha256_file",
    "validate_printable_response_artifact_plan",
]

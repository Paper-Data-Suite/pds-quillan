"""Application boundary for dry-run planning and managed PDS2 packet execution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any, Mapping, cast

from pds_core.rosters import StudentRecord
from pds_core.routing_models import ModuleWorkRef

from quillan.assignment_setup import load_canonical_assignment
from quillan.assignments import AssignmentConfigError, validate_assignment_config
from quillan.printable_response import PRINTABLE_RESPONSE_FILENAME
from quillan.printable_response_generation import (
    GeneratedPrintableResponsePacket,
    IdentityGenerators,
    build_printable_response_artifact_plan,
    execute_printable_response_artifact,
    select_printable_response_predecessors,
    sha256_file,
)
from quillan.roster_management import load_canonical_roster
from quillan.printable_response_records import (
    PrintableResponseRecordValidationError,
    validate_issuance_id,
)
from quillan.work_paths import quillan_work_paths, quillan_work_ref


@dataclass(frozen=True, slots=True)
class PrintableResponsePacketPlan:
    """Validated, genuinely non-writing inputs for one combined class packet."""

    workspace_root: Path
    work_ref: ModuleWorkRef
    class_id: str
    assignment_id: str
    assignment_title: str
    assignment: Mapping[str, Any]
    students: tuple[StudentRecord, ...]
    assignment_path: Path
    assignment_relative_path: str
    assignment_sha256: str
    roster_path: Path
    roster_relative_path: str
    roster_sha256: str
    output_path: Path
    output_relative_path: str
    output_sha256: str | None
    pages_per_student: int
    student_count: int
    planned_issuance_count: int
    total_page_count: int
    planned_route_count: int
    predecessor_count: int
    predecessor_issuance_ids: tuple[str | None, ...]
    initial_issuance_count: int
    regeneration_issuance_count: int
    target_exists: bool


def plan_printable_response_packet(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    pages_per_student: int = 1,
) -> PrintableResponsePacketPlan:
    """Validate canonical inputs and aggregate lineage without allocating IDs."""
    _validate_pages_per_student(pages_per_student)
    root = Path(workspace_root).resolve(strict=False)
    assignment = load_canonical_assignment(root, class_id, assignment_id)
    loaded_roster = load_canonical_roster(root, class_id)
    students = tuple(loaded_roster.roster.students)
    if not students:
        raise ValueError(
            "canonical roster must contain at least one student to generate a packet."
        )
    work_ref = quillan_work_ref(class_id, assignment_id)
    predecessors = select_printable_response_predecessors(root, work_ref, students)
    output_path = (
        quillan_work_paths(root, class_id, assignment_id).templates_dir
        / PRINTABLE_RESPONSE_FILENAME
    )
    target_exists = os.path.lexists(output_path)
    output_digest: str | None = None
    if target_exists:
        _require_ordinary_file(output_path, "Canonical printable-response output")
        output_digest = sha256_file(output_path)
    predecessor_count = sum(item is not None for item in predecessors)
    student_count = len(students)
    total_pages = student_count * pages_per_student
    return validate_printable_response_packet_plan(PrintableResponsePacketPlan(
        root,
        work_ref,
        class_id,
        assignment_id,
        cast(str, assignment.assignment["title"]),
        assignment.assignment,
        students,
        assignment.path,
        _relative_posix(assignment.path, root),
        sha256_file(assignment.path),
        loaded_roster.roster_path,
        _relative_posix(loaded_roster.roster_path, root),
        sha256_file(loaded_roster.roster_path),
        output_path,
        _relative_posix(output_path, root),
        output_digest,
        pages_per_student,
        student_count,
        student_count,
        total_pages,
        total_pages,
        predecessor_count,
        tuple(item.issuance_id if item is not None else None for item in predecessors),
        student_count - predecessor_count,
        predecessor_count,
        target_exists,
    ))


def validate_printable_response_packet_plan(
    value: object,
) -> PrintableResponsePacketPlan:
    """Strictly validate a complete nonmutating packet plan."""
    if type(value) is not PrintableResponsePacketPlan:
        raise ValueError("plan must be exactly a PrintableResponsePacketPlan.")
    plan = value
    if not isinstance(plan.workspace_root, Path) or not plan.workspace_root.is_absolute():
        raise ValueError("plan.workspace_root must be an absolute Path.")
    root = Path(os.path.abspath(plan.workspace_root))
    if root != plan.workspace_root:
        raise ValueError("plan.workspace_root must be canonical.")
    if not isinstance(plan.work_ref, ModuleWorkRef):
        raise ValueError("plan.work_ref must be a ModuleWorkRef.")
    try:
        expected_work = quillan_work_ref(plan.class_id, plan.assignment_id)
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"Invalid packet work identity: {error}") from error
    if plan.work_ref != expected_work:
        raise ValueError("Packet work_ref contradicts class_id or assignment_id.")
    expected_assignment = quillan_work_paths(
        root, plan.class_id, plan.assignment_id
    ).assignment_path
    expected_roster = root / "classes" / plan.class_id / "roster.csv"
    expected_output = (
        quillan_work_paths(root, plan.class_id, plan.assignment_id).templates_dir
        / PRINTABLE_RESPONSE_FILENAME
    )
    for path_actual, path_expected, label in (
        (plan.assignment_path, expected_assignment, "assignment_path"),
        (plan.roster_path, expected_roster, "roster_path"),
        (plan.output_path, expected_output, "output_path"),
    ):
        if (
            not isinstance(path_actual, Path)
            or not path_actual.is_absolute()
            or path_actual != path_expected
        ):
            raise ValueError(f"plan.{label} is not canonical.")
    for rel_actual, rel_expected, label in (
        (
            plan.assignment_relative_path,
            expected_assignment.relative_to(root).as_posix(),
            "assignment_relative_path",
        ),
        (
            plan.roster_relative_path,
            expected_roster.relative_to(root).as_posix(),
            "roster_relative_path",
        ),
        (
            plan.output_relative_path,
            expected_output.relative_to(root).as_posix(),
            "output_relative_path",
        ),
    ):
        if rel_actual != rel_expected:
            raise ValueError(f"plan.{label} is not canonical POSIX text.")
    for digest, label in (
        (plan.assignment_sha256, "assignment_sha256"),
        (plan.roster_sha256, "roster_sha256"),
    ):
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"plan.{label} must be lowercase SHA-256 text.")
    if not isinstance(plan.target_exists, bool):
        raise ValueError("plan.target_exists must be a boolean.")
    if plan.target_exists:
        if (
            not isinstance(plan.output_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", plan.output_sha256) is None
        ):
            raise ValueError("Existing target requires a lowercase SHA-256 digest.")
    elif plan.output_sha256 is not None:
        raise ValueError("Absent target requires a null output digest.")
    if not isinstance(plan.assignment, Mapping):
        raise ValueError("plan.assignment must be a mapping.")
    assignment = cast(dict[str, Any], dict(plan.assignment))
    try:
        validate_assignment_config(assignment)
    except (AssignmentConfigError, TypeError, ValueError) as error:
        raise ValueError(f"plan.assignment is invalid: {error}") from error
    if (
        assignment["assignment_id"] != plan.assignment_id
        or plan.class_id not in assignment["class_ids"]
        or plan.assignment_title != assignment["title"]
    ):
        raise ValueError("Packet assignment identity or title is contradictory.")
    if not isinstance(plan.students, tuple) or not plan.students:
        raise ValueError("plan.students must be a nonempty tuple.")
    if not all(
        isinstance(student, StudentRecord) and student.class_id == plan.class_id
        for student in plan.students
    ):
        raise ValueError("Packet students must be valid members of the planned class.")
    _validate_pages_per_student(plan.pages_per_student)
    expected_students = len(plan.students)
    expected_pages = expected_students * plan.pages_per_student
    if (
        plan.student_count != expected_students
        or plan.planned_issuance_count != expected_students
        or plan.total_page_count != expected_pages
        or plan.planned_route_count != expected_pages
    ):
        raise ValueError("Packet count fields are inconsistent.")
    if (
        not isinstance(plan.predecessor_issuance_ids, tuple)
        or len(plan.predecessor_issuance_ids) != expected_students
    ):
        raise ValueError("Packet predecessor IDs must align with students.")
    try:
        for predecessor_id in plan.predecessor_issuance_ids:
            if predecessor_id is not None:
                validate_issuance_id(predecessor_id)
    except PrintableResponseRecordValidationError as error:
        raise ValueError(str(error)) from error
    predecessor_count = sum(
        predecessor_id is not None
        for predecessor_id in plan.predecessor_issuance_ids
    )
    if (
        plan.predecessor_count != predecessor_count
        or plan.initial_issuance_count != expected_students - predecessor_count
        or plan.regeneration_issuance_count != predecessor_count
    ):
        raise ValueError("Packet predecessor counts are inconsistent.")
    return plan


def generate_printable_response_packet(
    plan: PrintableResponsePacketPlan,
    *,
    overwrite: bool = False,
    generators: IdentityGenerators = IdentityGenerators(),
) -> GeneratedPrintableResponsePacket:
    """Revalidate a dry plan, then execute one complete managed artifact."""
    plan = validate_printable_response_packet_plan(plan)
    if plan.target_exists and not overwrite:
        raise FileExistsError(
            "printable response packet already exists at "
            f"{plan.output_relative_path}; use --overwrite --yes to replace it."
        )
    if not plan.target_exists and os.path.lexists(plan.output_path):
        raise FileExistsError(
            "printable response packet appeared after planning; re-run planning."
        )
    current_assignment = load_canonical_assignment(
        plan.workspace_root, plan.class_id, plan.assignment_id
    )
    current_roster = load_canonical_roster(plan.workspace_root, plan.class_id)
    if (
        current_assignment.path != plan.assignment_path
        or current_roster.roster_path != plan.roster_path
        or sha256_file(current_assignment.path) != plan.assignment_sha256
        or sha256_file(current_roster.roster_path) != plan.roster_sha256
    ):
        raise ValueError(
            "Canonical assignment or roster changed after planning; re-run planning."
        )
    predecessors = select_printable_response_predecessors(
        plan.workspace_root, plan.work_ref, plan.students
    )
    if tuple(item.issuance_id if item is not None else None for item in predecessors) != (
        plan.predecessor_issuance_ids
    ):
        raise ValueError("Predecessor lineage changed after planning; re-run planning.")
    artifact = build_printable_response_artifact_plan(
        workspace_root=plan.workspace_root,
        work_ref=plan.work_ref,
        assignment=current_assignment.assignment,
        students=tuple(current_roster.roster.students),
        pages_per_student=plan.pages_per_student,
        output_path=plan.output_path,
        predecessors=predecessors,
        generators=generators,
    )
    return execute_printable_response_artifact(
        artifact,
        output_relative_path=plan.output_relative_path,
        expected_output_digest=plan.output_sha256,
        overwrite=overwrite,
    )


def _require_ordinary_file(path: Path, label: str) -> None:
    is_junction = getattr(path, "is_junction", None)
    if path.is_symlink() or bool(is_junction and is_junction()) or not path.is_file():
        raise ValueError(f"{label} must be an ordinary non-link file: {path}")


def _validate_pages_per_student(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("pages_per_student must be a positive integer.")


def _relative_posix(path: Path, workspace_root: Path) -> str:
    return path.resolve(strict=False).relative_to(workspace_root).as_posix()


__all__ = [
    "GeneratedPrintableResponsePacket",
    "PrintableResponsePacketPlan",
    "generate_printable_response_packet",
    "plan_printable_response_packet",
    "validate_printable_response_packet_plan",
]

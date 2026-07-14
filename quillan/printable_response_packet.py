"""Application services for canonical printable response class packets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from quillan.assignment_setup import load_canonical_assignment
from quillan.printable_response import (
    PRINTABLE_RESPONSE_FILENAME,
    generate_printable_responses_for_roster,
)
from quillan.roster_management import load_canonical_roster
from quillan.storage import assignment_templates_dir


@dataclass(frozen=True, slots=True)
class PrintableResponsePacketPlan:
    """Validated, non-writing inputs for one combined class packet."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    assignment_title: str
    assignment_path: Path
    assignment_relative_path: str
    roster_path: Path
    roster_relative_path: str
    output_path: Path
    output_relative_path: str
    pages_per_student: int
    student_count: int
    total_page_count: int
    target_exists: bool


@dataclass(frozen=True, slots=True)
class GeneratedPrintableResponsePacket:
    """Stable result of generating one combined class packet."""

    class_id: str
    assignment_id: str
    assignment_title: str
    output_path: Path
    output_relative_path: str
    pages_per_student: int
    student_count: int
    total_page_count: int
    replaced_existing: bool


def plan_printable_response_packet(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    pages_per_student: int = 1,
) -> PrintableResponsePacketPlan:
    """Validate canonical packet inputs without creating directories or files."""
    _validate_pages_per_student(pages_per_student)
    root = Path(workspace_root).resolve(strict=False)
    assignment = load_canonical_assignment(root, class_id, assignment_id)
    loaded_roster = load_canonical_roster(root, class_id)
    student_count = len(loaded_roster.roster.students)
    if student_count == 0:
        raise ValueError(
            "canonical roster must contain at least one student to generate a packet."
        )

    output_path = (
        assignment_templates_dir(root, class_id, assignment_id)
        / PRINTABLE_RESPONSE_FILENAME
    )
    return PrintableResponsePacketPlan(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title=cast(str, assignment.assignment["title"]),
        assignment_path=assignment.path,
        assignment_relative_path=_relative_posix(assignment.path, root),
        roster_path=loaded_roster.roster_path,
        roster_relative_path=_relative_posix(loaded_roster.roster_path, root),
        output_path=output_path,
        output_relative_path=_relative_posix(output_path, root),
        pages_per_student=pages_per_student,
        student_count=student_count,
        total_page_count=student_count * pages_per_student,
        target_exists=output_path.exists(),
    )


def generate_printable_response_packet(
    plan: PrintableResponsePacketPlan,
    *,
    overwrite: bool = False,
) -> GeneratedPrintableResponsePacket:
    """Enforce target protection and render one validated canonical packet."""
    target_exists = plan.output_path.exists()
    if target_exists and not overwrite:
        raise FileExistsError(
            f"printable response packet already exists at "
            f"{plan.output_relative_path}; use --overwrite --yes to replace it."
        )

    generated_path = generate_printable_responses_for_roster(
        plan.workspace_root,
        assignment_path=plan.assignment_path,
        roster_path=plan.roster_path,
        pages_per_student=plan.pages_per_student,
        class_label=plan.class_id,
    )
    if generated_path.resolve(strict=False) != plan.output_path.resolve(strict=False):
        raise ValueError(
            "printable response renderer returned an unexpected output path: "
            f"{generated_path}"
        )

    return GeneratedPrintableResponsePacket(
        class_id=plan.class_id,
        assignment_id=plan.assignment_id,
        assignment_title=plan.assignment_title,
        output_path=plan.output_path,
        output_relative_path=plan.output_relative_path,
        pages_per_student=plan.pages_per_student,
        student_count=plan.student_count,
        total_page_count=plan.total_page_count,
        replaced_existing=target_exists,
    )


def _validate_pages_per_student(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("pages_per_student must be a positive integer.")


def _relative_posix(path: Path, workspace_root: Path) -> str:
    return path.resolve(strict=False).relative_to(workspace_root).as_posix()

"""Non-interactive planning and writes for canonical class rosters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from pds_core.class_metadata import (
    ClassMetadata,
    ClassMetadataError,
    class_metadata_path,
    create_class_metadata,
    load_class_metadata_for_class,
    write_class_metadata_for_class,
)
from pds_core.classes import class_folder, load_class_roster, write_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.rosters import (
    ROSTER_REQUIRED_COLUMNS,
    Roster,
    StudentRecord,
    add_student_record,
    create_roster,
    load_roster,
    remove_student_record,
    replace_student_record,
)
from pds_core.school_years import get_active_school_year, validate_school_year


@dataclass(frozen=True, slots=True)
class RosterCreationPlan:
    """A fully validated, non-writing canonical roster creation."""

    workspace_root: Path
    source_path: Path
    roster_path: Path
    metadata_path: Path
    roster: Roster
    metadata: ClassMetadata
    target_exists: bool


@dataclass(frozen=True, slots=True)
class LoadedCanonicalRoster:
    """A canonical roster with optional class metadata state."""

    workspace_root: Path
    roster_path: Path
    metadata_path: Path
    roster: Roster
    metadata: ClassMetadata | None
    metadata_error: ClassMetadataError | None


@dataclass(frozen=True, slots=True)
class RosterMutationPlan:
    """A validated immutable replacement of one canonical roster."""

    workspace_root: Path
    roster_path: Path
    original: Roster
    roster: Roster
    student: StudentRecord
    action: str


def optional_roster_columns(roster: Roster) -> tuple[str, ...]:
    """Return optional columns in canonical CSV order."""
    return tuple(
        column for column in roster.columns if column not in ROSTER_REQUIRED_COLUMNS
    )


def parse_optional_fields(
    roster: Roster,
    fields: Sequence[str],
) -> Mapping[str, str]:
    """Validate repeatable ``column=value`` values against the roster schema."""
    allowed = set(optional_roster_columns(roster))
    parsed: dict[str, str] = {}
    for field in fields:
        if "=" not in field:
            raise ValueError(f"--field must use column=value: {field!r}.")
        column, value = field.split("=", 1)
        column = column.strip()
        if not column:
            raise ValueError("--field column must not be blank.")
        if column in ROSTER_REQUIRED_COLUMNS:
            raise ValueError(
                f"--field cannot set required roster column {column!r}."
            )
        if column not in allowed:
            raise ValueError(
                f"--field column {column!r} is not an existing optional column."
            )
        if column in parsed:
            raise ValueError(f"--field column {column!r} was supplied more than once.")
        parsed[column] = value.strip()
    return parsed


def student_record_from_values(
    roster: Roster,
    student_id: str,
    values: Mapping[str, str],
) -> StudentRecord:
    """Build a student while preserving the roster's optional schema."""
    return StudentRecord(
        class_id=roster.class_id,
        student_id=student_id.strip(),
        last_name=values["last_name"].strip(),
        first_name=values["first_name"].strip(),
        period=values["period"].strip(),
        extra_fields={
            column: values.get(column, "").strip()
            for column in optional_roster_columns(roster)
        },
    )


def plan_roster_creation(
    workspace_root: str | Path,
    class_id: str,
    source_path: str | Path,
    *,
    school_year: str | None = None,
) -> RosterCreationPlan:
    """Validate an external CSV and all canonical creation inputs without writes."""
    root = Path(workspace_root)
    expected_class_id = validate_identifier(class_id, "class_id")
    source = Path(source_path)
    roster = load_roster(source)
    if roster.class_id != expected_class_id:
        raise ValueError(
            f"source roster class_id {roster.class_id!r} does not match "
            f"requested class_id {expected_class_id!r}."
        )
    selected_year = (
        validate_school_year(school_year)
        if school_year is not None
        else get_active_school_year(root)
    )
    if selected_year is None:
        raise ValueError(
            "no active school year is open; supply --school-year or open a "
            "school year."
        )
    selected_year = validate_school_year(selected_year)
    now = datetime.now(timezone.utc)
    metadata = create_class_metadata(
        expected_class_id,
        selected_year,
        created_at=now,
        updated_at=now,
    )
    folder = class_folder(root, expected_class_id)
    return RosterCreationPlan(
        workspace_root=root,
        source_path=source,
        roster_path=folder.roster_path,
        metadata_path=folder.metadata_path,
        roster=roster,
        metadata=metadata,
        target_exists=folder.roster_path.exists() or folder.metadata_path.exists(),
    )


def plan_roster_creation_from_values(
    workspace_root: str | Path,
    class_id: str,
    students: Sequence[Mapping[str, str]],
    *,
    school_year: str,
) -> RosterCreationPlan:
    """Plan menu-entered roster values through the same creation boundary."""
    root = Path(workspace_root)
    roster = create_roster(class_id, students)
    selected_year = validate_school_year(school_year)
    now = datetime.now(timezone.utc)
    metadata = create_class_metadata(
        roster.class_id, selected_year, created_at=now, updated_at=now
    )
    folder = class_folder(root, roster.class_id)
    return RosterCreationPlan(
        workspace_root=root,
        source_path=Path("<interactive>"),
        roster_path=folder.roster_path,
        metadata_path=folder.metadata_path,
        roster=roster,
        metadata=metadata,
        target_exists=folder.roster_path.exists() or folder.metadata_path.exists(),
    )


def add_student_to_roster(roster: Roster, student: StudentRecord) -> Roster:
    """Validate and stage an in-memory addition for menu and adapters."""
    return add_student_record(roster, student)


def update_student_in_roster(roster: Roster, student: StudentRecord) -> Roster:
    """Validate and stage an in-memory stable-ID replacement."""
    return replace_student_record(roster, student)


def remove_student_from_roster(roster: Roster, student_id: str) -> Roster:
    """Validate and stage active-roster-only removal."""
    return remove_student_record(roster, student_id)


def write_roster_creation(
    plan: RosterCreationPlan,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Write a validated roster/metadata pair and clean up newly created halves."""
    roster_existed = plan.roster_path.exists()
    metadata_existed = plan.metadata_path.exists()
    class_dir_existed = plan.roster_path.parent.exists()
    if (roster_existed or metadata_existed) and not overwrite:
        raise ValueError(
            "canonical roster or class metadata already exists; use --overwrite --yes."
        )
    try:
        roster_path = write_class_roster(
            plan.workspace_root, plan.roster, overwrite=overwrite
        )
        metadata_path = write_class_metadata_for_class(
            plan.workspace_root, plan.metadata, overwrite=overwrite
        )
    except Exception:
        if not roster_existed:
            plan.roster_path.unlink(missing_ok=True)
        if not metadata_existed:
            plan.metadata_path.unlink(missing_ok=True)
        if not class_dir_existed:
            _remove_new_empty_class_directories(plan)
        raise
    return roster_path, metadata_path


def _remove_new_empty_class_directories(plan: RosterCreationPlan) -> None:
    class_dir = plan.roster_path.parent
    try:
        class_dir.rmdir()
    except OSError:
        pass


def load_canonical_roster(
    workspace_root: str | Path,
    class_id: str,
) -> LoadedCanonicalRoster:
    """Load a canonical roster and optional metadata without writing."""
    root = Path(workspace_root)
    validated_class_id = validate_identifier(class_id, "class_id")
    folder = class_folder(root, validated_class_id)
    roster = load_class_roster(root, validated_class_id)
    metadata: ClassMetadata | None = None
    metadata_error: ClassMetadataError | None = None
    if folder.metadata_path.is_file():
        try:
            metadata = load_class_metadata_for_class(root, validated_class_id)
        except ClassMetadataError as error:
            metadata_error = error
    return LoadedCanonicalRoster(
        workspace_root=root,
        roster_path=folder.roster_path,
        metadata_path=class_metadata_path(root, validated_class_id),
        roster=roster,
        metadata=metadata,
        metadata_error=metadata_error,
    )


def plan_add_student(
    workspace_root: str | Path,
    class_id: str,
    *,
    student_id: str,
    last_name: str,
    first_name: str,
    period: str,
    fields: Sequence[str] = (),
) -> RosterMutationPlan:
    """Plan an append using shared roster validation."""
    loaded = load_canonical_roster(workspace_root, class_id)
    extras = parse_optional_fields(loaded.roster, fields)
    student = student_record_from_values(
        loaded.roster,
        student_id,
        {"last_name": last_name, "first_name": first_name, "period": period, **extras},
    )
    updated = add_student_record(loaded.roster, student)
    return RosterMutationPlan(
        loaded.workspace_root,
        loaded.roster_path,
        loaded.roster,
        updated,
        student,
        "add",
    )


def plan_update_student(
    workspace_root: str | Path,
    class_id: str,
    student_id: str,
    *,
    last_name: str | None = None,
    first_name: str | None = None,
    period: str | None = None,
    fields: Sequence[str] = (),
) -> RosterMutationPlan:
    """Plan a stable-ID student replacement using shared validation."""
    loaded = load_canonical_roster(workspace_root, class_id)
    stable_id = validate_identifier(student_id.strip(), "student_id")
    existing = next(
        (student for student in loaded.roster.students if student.student_id == stable_id),
        None,
    )
    if existing is None:
        raise ValueError(f"student_id {stable_id!r} is not in the active roster.")
    extras = parse_optional_fields(loaded.roster, fields)
    if last_name is None and first_name is None and period is None and not fields:
        raise ValueError("at least one update field must be supplied.")
    values = {
        "last_name": existing.last_name if last_name is None else last_name,
        "first_name": existing.first_name if first_name is None else first_name,
        "period": existing.period if period is None else period,
        **existing.extra_fields,
        **extras,
    }
    replacement = student_record_from_values(loaded.roster, stable_id, values)
    updated = replace_student_record(loaded.roster, replacement)
    return RosterMutationPlan(
        loaded.workspace_root,
        loaded.roster_path,
        loaded.roster,
        updated,
        replacement,
        "update",
    )


def plan_remove_student(
    workspace_root: str | Path,
    class_id: str,
    student_id: str,
) -> RosterMutationPlan:
    """Plan removal from only the active canonical roster."""
    loaded = load_canonical_roster(workspace_root, class_id)
    stable_id = validate_identifier(student_id.strip(), "student_id")
    existing = next(
        (student for student in loaded.roster.students if student.student_id == stable_id),
        None,
    )
    if existing is None:
        raise ValueError(f"student_id {stable_id!r} is not in the active roster.")
    updated = remove_student_record(loaded.roster, stable_id)
    return RosterMutationPlan(
        loaded.workspace_root,
        loaded.roster_path,
        loaded.roster,
        updated,
        existing,
        "remove",
    )


def write_roster_mutation(plan: RosterMutationPlan) -> Path:
    """Replace only canonical roster.csv for a validated mutation."""
    return write_class_roster(plan.workspace_root, plan.roster, overwrite=True)

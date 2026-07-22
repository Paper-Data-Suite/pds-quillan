"""Direct, non-interactive canonical roster command handlers."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import sys

from pds_core.rosters import RosterError, RosterValidationError
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.roster_management import (
    RosterCreationPlan,
    RosterMutationPlan,
    load_canonical_roster,
    optional_roster_columns,
    plan_add_student,
    plan_remove_student,
    plan_roster_creation,
    plan_update_student,
    write_roster_creation,
    write_roster_mutation,
)
from quillan.roster_workflows import format_roster_for_display
from quillan.cli_app.output import workspace_relative_display


def _error(error: Exception) -> int:
    print(f"Error: {error}", file=sys.stderr)
    if isinstance(error, RosterValidationError):
        for issue in error.issues:
            location: list[str] = []
            if issue.row_number is not None:
                location.append(f"row {issue.row_number}")
            if issue.column:
                location.append(f"column {issue.column}")
            prefix = f"  {' / '.join(location)}: " if location else "  "
            print(f"{prefix}[{issue.code}] {issue.message}", file=sys.stderr)
    return 1


def _confirmation_error(args: argparse.Namespace) -> int | None:
    if not args.yes and not args.dry_run:
        return _error(ValueError("use --yes to confirm or --dry-run."))
    return None


def _optional_columns_label(columns: tuple[str, ...]) -> str:
    return ", ".join(columns) if columns else "none"


def _fields_label(student_fields: Mapping[str, str]) -> str:
    fields = dict(student_fields)
    if not fields:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in fields.items())


def _print_creation(plan: RosterCreationPlan, *, dry_run: bool) -> None:
    title = "Roster creation dry run:" if dry_run else "Created canonical roster:"
    print(title)
    print(f"Class ID: {plan.roster.class_id}")
    print(f"Source CSV: {plan.source_path}")
    print(f"School year: {plan.metadata.school_year}")
    print(f"Student count: {len(plan.roster.students)}")
    print(
        "Optional columns: "
        f"{_optional_columns_label(optional_roster_columns(plan.roster))}"
    )
    print(
        "Roster path: "
        f"{workspace_relative_display(plan.roster_path, plan.workspace_root)}"
    )
    print(
        "Class metadata path: "
        f"{workspace_relative_display(plan.metadata_path, plan.workspace_root)}"
    )
    print(f"Existing target: {'yes' if plan.target_exists else 'no'}")
    if dry_run:
        print("No files were written.")


def handle_roster_create(args: argparse.Namespace) -> int:
    """Plan and optionally create a canonical roster/metadata pair."""
    if args.overwrite and not args.yes:
        return _error(ValueError("--overwrite requires --yes."))
    confirmation_error = _confirmation_error(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        plan = plan_roster_creation(
            resolve_workspace_root(),
            args.class_id,
            args.input,
            school_year=args.school_year,
        )
        if args.dry_run:
            _print_creation(plan, dry_run=True)
            return 0
        if plan.target_exists and not args.overwrite:
            raise ValueError(
                "canonical roster or class metadata already exists; "
                "use --overwrite --yes."
            )
        write_roster_creation(plan, overwrite=args.overwrite)
        _print_creation(plan, dry_run=False)
        return 0
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)


def handle_roster_show(args: argparse.Namespace) -> int:
    """Show a canonical roster and optional metadata without writing."""
    try:
        loaded = load_canonical_roster(resolve_workspace_root(), args.class_id)
        print(
            format_roster_for_display(
                loaded.roster,
                workspace_relative_display(loaded.roster_path, loaded.workspace_root),
                metadata=loaded.metadata,
                metadata_path=workspace_relative_display(
                    loaded.metadata_path, loaded.workspace_root
                ),
                metadata_error=loaded.metadata_error,
            )
        )
        return 0
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)


def handle_roster_validate(args: argparse.Namespace) -> int:
    """Validate a canonical roster and any existing class metadata."""
    try:
        loaded = load_canonical_roster(resolve_workspace_root(), args.class_id)
        if loaded.metadata_error is not None:
            raise loaded.metadata_error
        print("Canonical roster is valid.")
        print(f"Class ID: {loaded.roster.class_id}")
        print(f"Student count: {len(loaded.roster.students)}")
        print(
            "Roster path: "
            f"{workspace_relative_display(loaded.roster_path, loaded.workspace_root)}"
        )
        print(
            "School year: "
            f"{loaded.metadata.school_year if loaded.metadata is not None else 'not set'}"
        )
        print(
            "Optional columns: "
            f"{_optional_columns_label(optional_roster_columns(loaded.roster))}"
        )
        return 0
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)


def _print_mutation(plan: RosterMutationPlan, *, dry_run: bool) -> None:
    action = {"add": "add", "update": "update", "remove": "remove"}[plan.action]
    print(f"Roster {action} {'dry run' if dry_run else 'complete'}:")
    print(f"Class ID: {plan.roster.class_id}")
    print(f"Student ID: {plan.student.student_id}")
    print(f"Student: {plan.student.first_name} {plan.student.last_name}")
    print(f"Period: {plan.student.period}")
    print(f"Optional fields: {_fields_label(plan.student.extra_fields)}")
    print(f"Resulting student count: {len(plan.roster.students)}")
    print(
        "Roster path: "
        f"{workspace_relative_display(plan.roster_path, plan.workspace_root)}"
    )
    if dry_run:
        print("No files were written.")


def _finish_mutation(args: argparse.Namespace, plan: RosterMutationPlan) -> int:
    if args.dry_run:
        _print_mutation(plan, dry_run=True)
        return 0
    write_roster_mutation(plan)
    _print_mutation(plan, dry_run=False)
    return 0


def handle_roster_add_student(args: argparse.Namespace) -> int:
    """Plan and optionally append one student to the active roster."""
    confirmation_error = _confirmation_error(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        plan = plan_add_student(
            resolve_workspace_root(),
            args.class_id,
            student_id=args.student_id,
            last_name=args.last_name,
            first_name=args.first_name,
            period=args.period,
            fields=args.field,
        )
        return _finish_mutation(args, plan)
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)


def handle_roster_update_student(args: argparse.Namespace) -> int:
    """Plan and optionally update one student without changing its ID."""
    confirmation_error = _confirmation_error(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        plan = plan_update_student(
            resolve_workspace_root(),
            args.class_id,
            args.student_id,
            last_name=args.last_name,
            first_name=args.first_name,
            period=args.period,
            fields=args.field,
        )
        return _finish_mutation(args, plan)
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)


_REMOVAL_BOUNDARY = (
    "Active-roster removal changes only roster.csv. It does not delete class "
    "metadata, assignments, submission manifests, review records, routed scans, "
    "source scans, printable PDFs, evidence files, teacher notes, observations, "
    "ratings, feedback, exports, reports, historical results, or other module data."
)


def handle_roster_remove_student(args: argparse.Namespace) -> int:
    """Plan and optionally remove one student only from active roster.csv."""
    confirmation_error = _confirmation_error(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        plan = plan_remove_student(
            resolve_workspace_root(), args.class_id, args.student_id
        )
        print(_REMOVAL_BOUNDARY)
        return _finish_mutation(args, plan)
    except (OSError, ValueError, RosterError, WorkspaceRootError) as error:
        return _error(error)

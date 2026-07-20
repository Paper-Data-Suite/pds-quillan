"""Direct, non-interactive printable response packet handler."""

from __future__ import annotations

import argparse

from pds_core.rosters import RosterError
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignments import AssignmentConfigError
from quillan.cli_app.printable_response_output import (
    print_generated_printable_response_packet,
    print_printable_response_packet_plan,
)
from quillan.printable_response_packet import (
    generate_printable_response_packet,
    plan_printable_response_packet,
)
from quillan.printable_response_generation import PrintableResponseGenerationError


def handle_printable_responses_generate(args: argparse.Namespace) -> int:
    """Validate, report, or generate one canonical combined class packet."""
    if args.overwrite and not args.yes:
        return _error(ValueError("--overwrite requires --yes."))
    if not args.yes and not args.dry_run:
        return _error(ValueError("use --yes to confirm or --dry-run."))

    try:
        plan = plan_printable_response_packet(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            pages_per_student=args.pages_per_student,
        )
        if args.dry_run:
            print_printable_response_packet_plan(plan)
            return 0
        result = generate_printable_response_packet(plan, overwrite=args.overwrite)
        print_generated_printable_response_packet(result)
        return 0 if result.success else 1
    except (
        AssignmentConfigError,
        OSError,
        PrintableResponseGenerationError,
        RosterError,
        ValueError,
        WorkspaceRootError,
    ) as error:
        return _error(error)


def _error(error: Exception) -> int:
    print(f"Error: {error}")
    return 1

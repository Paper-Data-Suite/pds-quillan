"""Direct Academic Work Registration command handlers."""

from __future__ import annotations

import argparse
import sys
from typing import cast

from pds_core.academic_work_registrations import (
    AcademicWorkIntent,
    AcademicWorkRegistration,
    AcademicWorkRegistrationLifecycle,
)
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_work_registration import (
    QuillanAcademicWorkRegistrationError,
    QuillanAcademicWorkRegistrationPartialSuccessError,
    load_current_quillan_academic_work_registration,
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)


def _print_registration(
    registration: AcademicWorkRegistration, *, status: str = "registered"
) -> None:
    print(f"module_id: {registration.work.module_id}")
    print(f"class_id: {registration.work.class_id}")
    print(f"assignment_id: {registration.work.work_id}")
    print(f"registration status: {status}")
    print(f"registration revision: {registration.registration_revision}")
    print(f"producer contract version: {registration.producer_contract_version}")
    print(f"title: {registration.title}")
    print(f"work kind: {registration.work_kind}")
    print(f"academic intent: {registration.academic_intent}")
    print(f"lifecycle: {registration.lifecycle}")
    print(f"created_at: {registration.created_at.isoformat()}")
    print(f"updated_at: {registration.updated_at.isoformat()}")
    print("source records:")
    for source in registration.source_records:
        contract_version = source.contract_version
        rendered_contract = "null" if contract_version is None else contract_version
        print(
            "  - "
            f"module_id={source.module_id}, record_kind={source.record_kind}, "
            f"record_id={source.record_id}, contract_version={rendered_contract}"
        )


def _error(action: str, error: Exception) -> int:
    print(f"Error: academic-work {action}: {error}", file=sys.stderr)
    if isinstance(error, QuillanAcademicWorkRegistrationPartialSuccessError):
        state = error.state
        print(
            "Warning: durable Core registry state may exist; validate the registry "
            "before retrying.",
            file=sys.stderr,
        )
        print(f"operation: {state.operation}", file=sys.stderr)
        if state.registration is not None:
            print(
                f"registration revision: {state.registration.registration_revision}",
                file=sys.stderr,
            )
        if state.canonical_path is not None:
            print(f"canonical path: {state.canonical_path}", file=sys.stderr)
        if state.current_selected is not None:
            selected = "yes" if state.current_selected else "no"
            print(f"current selected: {selected}", file=sys.stderr)
    return 1


def handle_academic_work_show(args: argparse.Namespace) -> int:
    """Show Core's current Academic Work Registration for one Quillan work."""
    try:
        registration = load_current_quillan_academic_work_registration(
            resolve_workspace_root(), args.class_id, args.assignment_id
        )
        if registration is None:
            print("module_id: quillan")
            print(f"class_id: {args.class_id}")
            print(f"assignment_id: {args.assignment_id}")
            print("registration status: not registered")
            return 1
        _print_registration(registration)
        return 0
    except (QuillanAcademicWorkRegistrationError, WorkspaceRootError) as error:
        return _error("show failed", error)


def handle_academic_work_register(args: argparse.Namespace) -> int:
    """Create revision 1 or exactly replay an existing registration."""
    try:
        result = register_quillan_academic_work(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            academic_intent=cast(AcademicWorkIntent, args.academic_intent),
            lifecycle=cast(AcademicWorkRegistrationLifecycle, args.lifecycle),
        )
        print(f"disposition: {result.disposition}")
        _print_registration(result.registration)
        return 0
    except (QuillanAcademicWorkRegistrationError, WorkspaceRootError) as error:
        return _error("registration failed", error)


def handle_academic_work_update(args: argparse.Namespace) -> int:
    """Update registration metadata using an explicit expected current revision."""
    try:
        result = update_quillan_academic_work_registration(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            academic_intent=cast(AcademicWorkIntent, args.academic_intent),
            lifecycle=cast(AcademicWorkRegistrationLifecycle, args.lifecycle),
            expected_current_revision=args.expected_current_revision,
        )
        print(f"disposition: {result.disposition}")
        _print_registration(result.registration)
        return 0
    except (QuillanAcademicWorkRegistrationError, WorkspaceRootError) as error:
        return _error("update failed", error)

"""Direct Core publication lifecycle command handlers."""

from __future__ import annotations

import argparse
import sys

from pds_core.publication_records import PublicationRecord, PublicationWithdrawal
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_result_publication import (
    AcademicResultPublicationResult,
    AcademicResultWithdrawalResult,
    PublicationPartialSuccessState,
    QuillanAcademicResultPublicationConflictError,
    QuillanAcademicResultPublicationError,
    QuillanAcademicResultPublicationIntegrityError,
    QuillanAcademicResultPublicationNotFoundError,
    QuillanAcademicResultPublicationPartialSuccessError,
    QuillanAcademicResultPublicationValidationError,
    QuillanAcademicResultPublicationWriteError,
    QuillanPublicationSeriesState,
    load_quillan_publication,
    load_quillan_publication_series_status,
    publish_quillan_academic_results,
    rebuild_full_academic_catalog,
    republish_quillan_academic_results_after_withdrawal,
    supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)


def _optional(value: object | None) -> str:
    return "none" if value is None else str(value)


def _print_publication(
    publication: PublicationRecord,
    withdrawal: PublicationWithdrawal | None,
    *,
    is_series_head: bool | None = None,
    is_current_selectable: bool | None = None,
) -> None:
    """Print privacy-safe canonical publication metadata."""
    print(f"module_id: {publication.work.module_id}")
    print(f"class_id: {publication.work.class_id}")
    print(f"assignment_id: {publication.work.work_id}")
    print(f"publication id: {publication.publication_id}")
    print(f"publication kind: {publication.publication_kind}")
    print(f"record set id: {publication.record_set_id}")
    print(f"record set revision: {publication.record_set_revision}")
    print(f"capabilities: {', '.join(publication.capabilities)}")
    print(f"manifest contract: {publication.manifest_contract_version}")
    print(f"manifest path: {publication.manifest_path}")
    print(f"manifest sha256: {publication.manifest_digest}")
    print(
        "registration revision: "
        f"{_optional(publication.academic_work_registration_revision)}"
    )
    print(
        "supersedes publication id: "
        f"{_optional(publication.supersedes_publication_id)}"
    )
    print(f"published_at: {publication.published_at.isoformat()}")
    print(f"withdrawn: {'yes' if withdrawal is not None else 'no'}")
    if withdrawal is not None:
        print(f"withdrawn_at: {withdrawal.withdrawn_at.isoformat()}")
    if is_series_head is not None:
        print(f"series head: {'yes' if is_series_head else 'no'}")
    if is_current_selectable is not None:
        print(
            "current selectable: "
            f"{'yes' if is_current_selectable else 'no'}"
        )


def _print_series_state(state: QuillanPublicationSeriesState) -> None:
    print(f"module_id: {state.work.module_id}")
    print(f"class_id: {state.work.class_id}")
    print(f"assignment_id: {state.work.work_id}")
    print(
        "producer head revision: "
        f"{_optional(state.producer_head_revision)}"
    )
    print(f"publication count: {len(state.publications)}")
    print(f"withdrawal count: {len(state.withdrawals)}")
    print(
        "canonical series head: "
        f"{_optional(None if state.core_head is None else state.core_head.publication_id)}"
    )
    print(
        "current selectable publication: "
        f"{_optional(None if state.current_selectable_publication is None else state.current_selectable_publication.publication_id)}"
    )
    print(
        "catalog available: "
        f"{'yes' if state.derived_catalog_available else 'no'}"
    )


def _print_publication_result(result: AcademicResultPublicationResult) -> None:
    print(f"operation: {result.operation}")
    print(f"disposition: {result.disposition}")
    print("producer compatibility: compatible")
    print("catalog reconciliation: verified")
    _print_publication(
        result.publication,
        result.withdrawal,
        is_series_head=result.catalog.publication.is_series_head,
        is_current_selectable=result.catalog.publication.is_current_selectable,
    )


def _print_withdrawal_result(result: AcademicResultWithdrawalResult) -> None:
    print("operation: withdraw")
    print(f"disposition: {result.disposition}")
    print(
        "withdrawal manifest verification: "
        f"{result.manifest_verification}"
    )
    print("catalog reconciliation: verified")
    _print_publication(
        result.publication,
        result.withdrawal,
        is_series_head=result.catalog.publication.is_series_head,
        is_current_selectable=result.catalog.publication.is_current_selectable,
    )


def _error_summary(error: Exception) -> str:
    if isinstance(error, QuillanAcademicResultPublicationValidationError):
        return "invalid publication request"
    if isinstance(error, QuillanAcademicResultPublicationNotFoundError):
        return "required publication state was not found"
    if isinstance(error, QuillanAcademicResultPublicationConflictError):
        return "publication state conflicts with the requested operation"
    if isinstance(error, QuillanAcademicResultPublicationIntegrityError):
        return "publication state failed integrity checks"
    if isinstance(error, QuillanAcademicResultPublicationWriteError):
        return "publication state could not be safely written or reconciled"
    if isinstance(error, WorkspaceRootError):
        return "the Paper Data Suite workspace could not be resolved"
    return "publication operation failed"


def _print_partial_state(state: PublicationPartialSuccessState) -> None:
    print(
        f"canonical state: {state.canonical_state}",
        file=sys.stderr,
    )
    if state.publication is not None:
        print(
            f"publication id: {state.publication.publication_id}",
            file=sys.stderr,
        )
    if state.manifest is not None:
        print(
            f"producer revision: {state.manifest.revision}",
            file=sys.stderr,
        )
        print(
            f"manifest path: {state.manifest.relative_path}",
            file=sys.stderr,
        )
        print(
            f"manifest sha256: {state.manifest.sha256}",
            file=sys.stderr,
        )
    if state.withdrawal is not None:
        print("withdrawal durable: yes", file=sys.stderr)
        print(
            f"withdrawn_at: {state.withdrawal.withdrawn_at.isoformat()}",
            file=sys.stderr,
        )
    if state.withdrawal_manifest_verification is not None:
        print(
            "withdrawal manifest verification: "
            f"{state.withdrawal_manifest_verification}",
            file=sys.stderr,
        )
    print(
        "catalog rebuild attempted: "
        f"{'yes' if state.catalog_rebuild_attempted else 'no'}",
        file=sys.stderr,
    )
    print(
        "catalog replacement completed: "
        f"{'yes' if state.catalog_replacement_completed else 'no'}",
        file=sys.stderr,
    )
    print(
        "catalog verification completed: "
        f"{'yes' if state.catalog_verification_completed else 'no'}",
        file=sys.stderr,
    )
    print(
        f"next action: {state.recommended_next_action}",
        file=sys.stderr,
    )


def _error(action: str, error: Exception) -> int:
    """Render a bounded privacy-safe CLI error."""
    print(
        f"Error: publication {action}: {_error_summary(error)}.",
        file=sys.stderr,
    )
    if isinstance(error, QuillanAcademicResultPublicationPartialSuccessError):
        print(
            "Warning: immutable producer/Core state may already be durable.",
            file=sys.stderr,
        )
        _print_partial_state(error.state)
    return 1


def handle_publication_status(args: argparse.Namespace) -> int:
    try:
        state = load_quillan_publication_series_status(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
        )
        _print_series_state(state)
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("status failed", error)


def handle_publication_list(args: argparse.Namespace) -> int:
    try:
        state = load_quillan_publication_series_status(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
        )
        if not state.publications:
            print("publications: none")
            return 0
        print(f"publications: {len(state.publications)}")
        withdrawal_by_id = {
            item.publication_id: item for item in state.withdrawals
        }
        for index, publication in enumerate(state.publications):
            if index:
                print()
            _print_publication(
                publication,
                withdrawal_by_id.get(publication.publication_id),
                is_series_head=(
                    state.core_head is not None
                    and state.core_head.publication_id
                    == publication.publication_id
                ),
                is_current_selectable=(
                    state.current_selectable_publication is not None
                    and state.current_selectable_publication.publication_id
                    == publication.publication_id
                ),
            )
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("list failed", error)


def handle_publication_show(args: argparse.Namespace) -> int:
    try:
        root = resolve_workspace_root()
        publication, withdrawal = load_quillan_publication(
            root,
            args.class_id,
            args.assignment_id,
            args.publication_id,
        )
        state = load_quillan_publication_series_status(
            root,
            args.class_id,
            args.assignment_id,
        )
        _print_publication(
            publication,
            withdrawal,
            is_series_head=(
                state.core_head is not None
                and state.core_head.publication_id
                == publication.publication_id
            ),
            is_current_selectable=(
                state.current_selectable_publication is not None
                and state.current_selectable_publication.publication_id
                == publication.publication_id
            ),
        )
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("show failed", error)


def handle_publication_publish(args: argparse.Namespace) -> int:
    try:
        result = publish_quillan_academic_results(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            manifest_revision=args.revision,
        )
        _print_publication_result(result)
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("publish failed", error)


def handle_publication_supersede(args: argparse.Namespace) -> int:
    try:
        result = supersede_quillan_academic_results(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            manifest_revision=args.revision,
            expected_current_publication_id=(
                args.expected_current_publication_id
            ),
        )
        _print_publication_result(result)
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("supersede failed", error)


def handle_publication_republish_after_withdrawal(
    args: argparse.Namespace,
) -> int:
    try:
        result = republish_quillan_academic_results_after_withdrawal(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            expected_withdrawn_head_publication_id=(
                args.expected_current_publication_id
            ),
        )
        _print_publication_result(result)
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("republish-after-withdrawal failed", error)


def handle_publication_withdraw(args: argparse.Namespace) -> int:
    try:
        result = withdraw_quillan_academic_result_publication(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            publication_id=args.publication_id,
            reason=args.reason,
        )
        _print_withdrawal_result(result)
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("withdraw failed", error)


def handle_publication_rebuild_catalog(args: argparse.Namespace) -> int:
    del args
    try:
        rebuild_full_academic_catalog(resolve_workspace_root())
        print("catalog rebuild: complete")
        return 0
    except (
        QuillanAcademicResultPublicationError,
        WorkspaceRootError,
        ValueError,
    ) as error:
        return _error("rebuild-catalog failed", error)


__all__ = [
    "handle_publication_list",
    "handle_publication_publish",
    "handle_publication_rebuild_catalog",
    "handle_publication_republish_after_withdrawal",
    "handle_publication_show",
    "handle_publication_status",
    "handle_publication_supersede",
    "handle_publication_withdraw",
]

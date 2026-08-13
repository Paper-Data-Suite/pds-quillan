"""Quillan-owned Academic Work Registration for managed assignments."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Final

from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationConflictError as CoreStorageConflictError,
)
from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationIntegrityError as CoreStorageIntegrityError,
)
from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationNotFoundError as CoreStorageNotFoundError,
)
from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationReadError as CoreStorageReadError,
)
from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationWriteError as CoreStorageWriteError,
)
from pds_core.academic_work_registration_storage import (
    load_current_academic_work_registration,
)
from pds_core.academic_work_registrations import (
    ACADEMIC_WORK_INTENTS,
    ACADEMIC_WORK_REGISTRATION_LIFECYCLES,
    AcademicWorkIntent,
    AcademicWorkRegistration,
    AcademicWorkRegistrationLifecycle,
    AcademicWorkRegistrationValidationError as CoreModelValidationError,
)
from pds_core.registry_services import (
    AcademicWorkRegistrationRequest,
    AcademicWorkRegistrationServiceResult,
    RegistryServiceConflictError,
    RegistryServiceIntegrityError,
    RegistryServiceNotFoundError,
    RegistryServicePartialState,
    RegistryServicePartialSuccessError,
    RegistryServiceValidationError,
    RegistryServiceWriteError,
    register_academic_work,
    update_academic_work_registration,
)
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef

from quillan._path_safety import is_link_like
from quillan.pds_contract import (
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_MODULE_ID,
)
from quillan.record_context import (
    QuillanRecordContextError,
    canonical_workspace_root,
    load_quillan_assignment_context,
)
from quillan.work_paths import quillan_work_paths, quillan_work_ref

QUILLAN_ACADEMIC_WORK_KIND: Final[str] = "assignment"
QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND: Final[str] = "assignment"
QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION: Final[str] = "2"

SUPPORTED_ACADEMIC_INTENTS: tuple[AcademicWorkIntent, ...] = (
    "formative",
    "summative",
    "diagnostic",
    "practice",
    "feedback_only",
    "reporting_only",
)
SUPPORTED_ACADEMIC_WORK_LIFECYCLES: tuple[
    AcademicWorkRegistrationLifecycle, ...
] = ("planned", "active", "closed", "cancelled")


class QuillanAcademicWorkRegistrationError(Exception):
    """Base error for Quillan's Academic Work Registration boundary."""


class QuillanAcademicWorkRegistrationValidationError(
    QuillanAcademicWorkRegistrationError, ValueError
):
    """Caller input or managed assignment state is invalid."""


class QuillanAcademicWorkRegistrationNotFoundError(
    QuillanAcademicWorkRegistrationError
):
    """Requested managed work or canonical registration does not exist."""


class QuillanAcademicWorkRegistrationConflictError(
    QuillanAcademicWorkRegistrationError
):
    """Existing canonical state conflicts with the requested operation."""


class QuillanAcademicWorkRegistrationIntegrityError(
    QuillanAcademicWorkRegistrationError
):
    """Canonical registry state cannot be reconciled safely."""


class QuillanAcademicWorkRegistrationWriteError(
    QuillanAcademicWorkRegistrationError
):
    """Core could not durably complete the requested operation."""


class QuillanAcademicWorkRegistrationPartialSuccessError(
    QuillanAcademicWorkRegistrationError
):
    """Core left durable state while completion remained uncertain."""

    def __init__(self, message: str, state: RegistryServicePartialState) -> None:
        super().__init__(message)
        self.state = state


@dataclass(frozen=True, slots=True)
class ManagedAssignmentRegistrationContext:
    """Validated minimal snapshot used to build one registration request."""

    work: ModuleWorkRef
    work_root: Path
    assignment_path: Path
    title: str


def load_managed_assignment_registration_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> ManagedAssignmentRegistrationContext:
    """Load one existing canonical Quillan assignment eligible for registration."""
    try:
        root = canonical_workspace_root(workspace_root)
        work = quillan_work_ref(class_id, assignment_id)
        paths = quillan_work_paths(root, class_id, assignment_id)
    except QuillanRecordContextError as error:
        raise QuillanAcademicWorkRegistrationValidationError(str(error)) from error
    except (TypeError, ValueError) as error:
        raise QuillanAcademicWorkRegistrationValidationError(str(error)) from error

    if not os.path.lexists(paths.work_root):
        raise QuillanAcademicWorkRegistrationNotFoundError(
            f"Managed Quillan work does not exist: {paths.work_root}"
        )
    if is_link_like(paths.work_root) or not paths.work_root.is_dir():
        raise QuillanAcademicWorkRegistrationValidationError(
            "Managed Quillan work root must be an ordinary non-link directory."
        )
    if not os.path.lexists(paths.assignment_path):
        raise QuillanAcademicWorkRegistrationNotFoundError(
            f"Assignment config not found: {paths.assignment_path}"
        )
    if is_link_like(paths.assignment_path) or not paths.assignment_path.is_file():
        raise QuillanAcademicWorkRegistrationValidationError(
            "assignment.json must be an ordinary non-link file."
        )
    try:
        context = load_quillan_assignment_context(root, work)
    except QuillanRecordContextError as error:
        raise QuillanAcademicWorkRegistrationValidationError(str(error)) from error

    assignment = context.assignment
    if assignment["assignment_id"] != work.work_id:
        raise QuillanAcademicWorkRegistrationValidationError(
            "assignment.json assignment_id does not match its managed work identity."
        )
    class_ids = assignment["class_ids"]
    if not isinstance(class_ids, tuple) or work.class_id not in class_ids:
        raise QuillanAcademicWorkRegistrationValidationError(
            "Selected class_id is not represented by assignment.json class_ids."
        )
    title = assignment["title"]
    if not isinstance(title, str):
        raise QuillanAcademicWorkRegistrationValidationError(
            "assignment.json title must be a string."
        )
    return ManagedAssignmentRegistrationContext(
        work=work,
        work_root=context.paths.work_root,
        assignment_path=context.paths.assignment_path,
        title=title,
    )


def build_quillan_academic_work_registration_request(
    context: ManagedAssignmentRegistrationContext,
    *,
    academic_intent: AcademicWorkIntent,
    lifecycle: AcademicWorkRegistrationLifecycle,
) -> AcademicWorkRegistrationRequest:
    """Purely map a validated Quillan assignment context to Core's request."""
    if not isinstance(context, ManagedAssignmentRegistrationContext):
        raise QuillanAcademicWorkRegistrationValidationError(
            "context must be a ManagedAssignmentRegistrationContext."
        )
    if context.work.module_id != QUILLAN_MODULE_ID:
        raise QuillanAcademicWorkRegistrationValidationError(
            'work.module_id must be exactly "quillan".'
        )
    if academic_intent not in ACADEMIC_WORK_INTENTS:
        raise QuillanAcademicWorkRegistrationValidationError(
            "academic_intent must be one of: "
            + ", ".join(SUPPORTED_ACADEMIC_INTENTS)
            + "."
        )
    if lifecycle not in ACADEMIC_WORK_REGISTRATION_LIFECYCLES:
        raise QuillanAcademicWorkRegistrationValidationError(
            "lifecycle must be one of: "
            + ", ".join(SUPPORTED_ACADEMIC_WORK_LIFECYCLES)
            + "."
        )
    try:
        return AcademicWorkRegistrationRequest(
            work=context.work,
            producer_contract_version=QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
            title=context.title,
            work_kind=QUILLAN_ACADEMIC_WORK_KIND,
            academic_intent=academic_intent,
            lifecycle=lifecycle,
            source_records=(
                ModuleRecordRef(
                    module_id=QUILLAN_MODULE_ID,
                    record_kind=QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
                    record_id=context.work.work_id,
                    contract_version=QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
                ),
            ),
        )
    except (RegistryServiceValidationError, TypeError, ValueError) as error:
        raise QuillanAcademicWorkRegistrationValidationError(str(error)) from error


def load_current_quillan_academic_work_registration(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AcademicWorkRegistration | None:
    """Load Core's explicit current registration by exact Quillan work identity."""
    try:
        work = quillan_work_ref(class_id, assignment_id)
        return load_current_academic_work_registration(workspace_root, work)
    except Exception as error:
        _raise_normalized_storage_error(error)
    raise AssertionError("unreachable")


def register_quillan_academic_work(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    academic_intent: AcademicWorkIntent,
    lifecycle: AcademicWorkRegistrationLifecycle,
) -> AcademicWorkRegistrationServiceResult:
    """Create revision 1 or return Core's exact existing registration."""
    context = load_managed_assignment_registration_context(
        workspace_root, class_id, assignment_id
    )
    request = build_quillan_academic_work_registration_request(
        context, academic_intent=academic_intent, lifecycle=lifecycle
    )
    try:
        result = register_academic_work(workspace_root, request)
    except Exception as error:
        _raise_normalized_service_error(error)
    if result.disposition not in {"created", "existing"}:
        raise QuillanAcademicWorkRegistrationIntegrityError(
            f"Core returned unexpected registration disposition: {result.disposition}."
        )
    if (
        result.disposition == "created"
        and result.registration.registration_revision != 1
    ):
        raise QuillanAcademicWorkRegistrationIntegrityError(
            "Initial registration did not create revision 1."
        )
    _verify_current(workspace_root, context.work, result.registration)
    return result


def update_quillan_academic_work_registration(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    academic_intent: AcademicWorkIntent,
    lifecycle: AcademicWorkRegistrationLifecycle,
    expected_current_revision: int,
) -> AcademicWorkRegistrationServiceResult:
    """Update registration metadata with Core's optimistic revision check."""
    if (
        isinstance(expected_current_revision, bool)
        or not isinstance(expected_current_revision, int)
        or expected_current_revision < 1
    ):
        raise QuillanAcademicWorkRegistrationValidationError(
            "expected_current_revision must be a positive integer."
        )
    context = load_managed_assignment_registration_context(
        workspace_root, class_id, assignment_id
    )
    request = build_quillan_academic_work_registration_request(
        context, academic_intent=academic_intent, lifecycle=lifecycle
    )
    try:
        result = update_academic_work_registration(
            workspace_root,
            request,
            expected_current_revision=expected_current_revision,
        )
    except Exception as error:
        _raise_normalized_service_error(error)
    if result.disposition not in {"updated", "existing"}:
        raise QuillanAcademicWorkRegistrationIntegrityError(
            f"Core returned unexpected update disposition: {result.disposition}."
        )
    _verify_current(workspace_root, context.work, result.registration)
    return result


def _verify_current(
    workspace_root: str | Path,
    work: ModuleWorkRef,
    expected: AcademicWorkRegistration,
) -> None:
    try:
        current = load_current_academic_work_registration(workspace_root, work)
    except Exception as error:
        _raise_normalized_storage_error(error)
    if current != expected:
        raise QuillanAcademicWorkRegistrationIntegrityError(
            "Core's current registration does not equal the service result."
        )


def _raise_normalized_service_error(error: Exception) -> None:
    if isinstance(error, RegistryServicePartialSuccessError):
        raise QuillanAcademicWorkRegistrationPartialSuccessError(
            str(error), error.state
        ) from error
    mappings = (
        (
            RegistryServiceValidationError,
            QuillanAcademicWorkRegistrationValidationError,
        ),
        (RegistryServiceNotFoundError, QuillanAcademicWorkRegistrationNotFoundError),
        (RegistryServiceConflictError, QuillanAcademicWorkRegistrationConflictError),
        (RegistryServiceIntegrityError, QuillanAcademicWorkRegistrationIntegrityError),
        (RegistryServiceWriteError, QuillanAcademicWorkRegistrationWriteError),
    )
    for core_type, quillan_type in mappings:
        if isinstance(error, core_type):
            raise quillan_type(str(error)) from error
    raise error


def _raise_normalized_storage_error(error: Exception) -> None:
    mappings = (
        (CoreModelValidationError, QuillanAcademicWorkRegistrationValidationError),
        (CoreStorageNotFoundError, QuillanAcademicWorkRegistrationNotFoundError),
        (CoreStorageConflictError, QuillanAcademicWorkRegistrationConflictError),
        (CoreStorageIntegrityError, QuillanAcademicWorkRegistrationIntegrityError),
        (CoreStorageWriteError, QuillanAcademicWorkRegistrationWriteError),
        (CoreStorageReadError, QuillanAcademicWorkRegistrationIntegrityError),
        (TypeError, QuillanAcademicWorkRegistrationValidationError),
        (ValueError, QuillanAcademicWorkRegistrationValidationError),
    )
    for core_type, quillan_type in mappings:
        if isinstance(error, core_type):
            raise quillan_type(str(error)) from error
    raise error


__all__ = [
    "ManagedAssignmentRegistrationContext",
    "QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION",
    "QUILLAN_ACADEMIC_WORK_KIND",
    "QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION",
    "QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND",
    "QuillanAcademicWorkRegistrationConflictError",
    "QuillanAcademicWorkRegistrationError",
    "QuillanAcademicWorkRegistrationIntegrityError",
    "QuillanAcademicWorkRegistrationNotFoundError",
    "QuillanAcademicWorkRegistrationPartialSuccessError",
    "QuillanAcademicWorkRegistrationValidationError",
    "QuillanAcademicWorkRegistrationWriteError",
    "SUPPORTED_ACADEMIC_INTENTS",
    "SUPPORTED_ACADEMIC_WORK_LIFECYCLES",
    "build_quillan_academic_work_registration_request",
    "load_current_quillan_academic_work_registration",
    "load_managed_assignment_registration_context",
    "register_quillan_academic_work",
    "update_quillan_academic_work_registration",
]

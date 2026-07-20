"""Safe persistence for immutable Quillan printable-response records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any, cast

from pds_core.classes import load_class_roster
from pds_core.rosters import RosterError, student_display_name
from pds_core.routing_models import (
    ModuleWorkRef,
    RoutingModelError,
    validate_module_work_ref,
)

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.printable_response_records import (
    PrintableResponseIssuance,
    PrintableResponsePage,
    PrintableResponsePageContext,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    printable_response_issuance_from_mapping,
    printable_response_page_from_mapping,
    transition_printable_response_lifecycle,
    validate_issuance_id,
    validate_page_id,
    validate_printable_response_record_set,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    _preflight_directories,
    preflight_work_file_destination,
    quillan_work_paths,
    response_page_issuance_path,
    response_page_record_path,
)


class PrintableResponsePersistenceError(Exception):
    """Base error for printable-response persistence operations."""


class PrintableResponsePersistenceValidationError(PrintableResponsePersistenceError):
    """Raised when a supplied record set or work identity is invalid."""


class PrintableResponseRecordCollisionError(PrintableResponsePersistenceError):
    """Raised when any immutable record destination already exists."""


class PrintableResponseReadError(PrintableResponsePersistenceError):
    """Raised when an exact record cannot be decoded or read safely."""


class PrintableResponseNotFoundError(PrintableResponseReadError):
    """Raised when an exact requested record is absent."""


class PrintableResponseIntegrityError(PrintableResponsePersistenceError):
    """Raised when persisted identities or record membership disagree."""


class PrintableResponseRecordSetWriteError(PrintableResponsePersistenceError):
    """Raised when exclusive record-set creation does not complete."""


class PrintableResponseRollbackError(
    PrintableResponseIntegrityError, PrintableResponseRecordSetWriteError
):
    """Raised when current-operation files cannot be completely rolled back."""


class PrintableResponseLifecycleError(PrintableResponsePersistenceError):
    """Raised when a persisted lifecycle cannot be transitioned safely."""


class PrintableResponseLifecycleCleanupError(PrintableResponseLifecycleError):
    """Raised when an abandoned lifecycle temporary file cannot be removed."""


class PrintableResponseRevisionConflictError(PrintableResponseLifecycleError):
    """Raised when the caller's expected issuance revision is stale."""


@dataclass(frozen=True, slots=True)
class PersistedPrintableResponseRecordSet:
    record_set: PrintableResponseRecordSet
    issuance_path: Path
    page_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class _CreatedRecord:
    path: Path
    expected_bytes: bytes


def _validated_quillan_work_ref(value: object) -> ModuleWorkRef:
    if not isinstance(value, ModuleWorkRef):
        raise PrintableResponsePersistenceValidationError(
            "work_ref must be a ModuleWorkRef."
        )
    try:
        validated = validate_module_work_ref(value)
    except (RoutingModelError, TypeError, AttributeError) as error:
        raise PrintableResponsePersistenceValidationError(
            f"Invalid work_ref: {error}"
        ) from error
    if validated.module_id != QUILLAN_MODULE_ID:
        raise PrintableResponsePersistenceValidationError(
            f"work_ref.module_id must be {QUILLAN_MODULE_ID!r}."
        )
    return validated


def canonical_printable_response_json(value: Mapping[str, Any]) -> bytes:
    """Encode a record as deterministic strict UTF-8 JSON with one newline."""
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise PrintableResponsePersistenceValidationError(
            f"Record is not strict JSON: {error}"
        ) from error
    return f"{text}\n".encode("utf-8")


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrintableResponseReadError(f"Duplicate JSON object key: {key!r}.")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise PrintableResponseReadError(f"Non-standard JSON constant is forbidden: {value}.")


def _strict_json_bytes(data: bytes, path: Path) -> Mapping[str, Any]:
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except PrintableResponseReadError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PrintableResponseReadError(f"Invalid UTF-8 JSON record {path}: {error}") from error
    if not isinstance(value, dict):
        raise PrintableResponseReadError(f"Record must be a JSON object: {path}")
    return cast(Mapping[str, Any], value)


def _record_relative_path(path: Path, work_root: Path) -> Path:
    try:
        return path.relative_to(work_root)
    except ValueError as error:
        raise PrintableResponseIntegrityError(
            f"Record path escapes exact Quillan work root: {path}"
        ) from error


def _preflight_exact_file(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    path: Path,
) -> None:
    try:
        work_root = quillan_work_paths(
            workspace_root, work_ref.class_id, work_ref.work_id
        ).work_root
        preflight_work_file_destination(
            workspace_root, work_ref, _record_relative_path(path, work_root)
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseIntegrityError(str(error)) from error


def _read_exact_record(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    path: Path,
) -> Mapping[str, Any]:
    value, _ = _read_exact_record_with_bytes(workspace_root, work_ref, path)
    return value


def _read_exact_record_with_bytes(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    path: Path,
) -> tuple[Mapping[str, Any], bytes]:
    _preflight_exact_file(workspace_root, work_ref, path)
    if not path.exists():
        raise PrintableResponseNotFoundError(f"Printable-response record not found: {path}")
    if _is_link_like(path) or not path.is_file():
        raise PrintableResponseReadError(f"Record is not an ordinary non-link file: {path}")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PrintableResponseReadError(f"Could not read record {path}: {error}") from error
    return _strict_json_bytes(data, path), data


def _load_printable_response_issuance_with_bytes(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance_id: str,
) -> tuple[PrintableResponseIssuance, bytes]:
    issuance_id = validate_issuance_id(issuance_id)
    try:
        path = response_page_issuance_path(workspace_root, work_ref, issuance_id)
    except QuillanWorkPathError as error:
        raise PrintableResponseIntegrityError(str(error)) from error
    try:
        mapping, data = _read_exact_record_with_bytes(workspace_root, work_ref, path)
        issuance = printable_response_issuance_from_mapping(mapping)
    except (PrintableResponseRecordValidationError, TypeError, AttributeError) as error:
        raise PrintableResponseReadError(f"Invalid issuance record {path}: {error}") from error
    if issuance.issuance_id != issuance_id:
        raise PrintableResponseIntegrityError("Stored issuance_id does not match its filename.")
    if (issuance.class_id, issuance.assignment_id) != (
        work_ref.class_id,
        work_ref.work_id,
    ):
        raise PrintableResponseIntegrityError("Issuance identity does not match work_ref.")
    return issuance, data


def load_printable_response_issuance(
    workspace_root: str | Path,
    work_ref: object,
    issuance_id: str,
) -> PrintableResponseIssuance:
    """Load only one exact validated issuance record."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    issuance, _ = _load_printable_response_issuance_with_bytes(
        workspace_root, validated_work_ref, issuance_id
    )
    return issuance


def load_printable_response_page(
    workspace_root: str | Path,
    work_ref: object,
    page_id: str,
) -> PrintableResponsePage:
    """Load only one exact validated immutable page record."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    page_id = validate_page_id(page_id)
    try:
        path = response_page_record_path(workspace_root, validated_work_ref, page_id)
    except QuillanWorkPathError as error:
        raise PrintableResponseIntegrityError(str(error)) from error
    try:
        page = printable_response_page_from_mapping(
            _read_exact_record(workspace_root, validated_work_ref, path)
        )
    except (PrintableResponseRecordValidationError, TypeError, AttributeError) as error:
        raise PrintableResponseReadError(f"Invalid page record {path}: {error}") from error
    if page.page_id != page_id:
        raise PrintableResponseIntegrityError("Stored page_id does not match its filename.")
    if (page.class_id, page.assignment_id) != (
        validated_work_ref.class_id,
        validated_work_ref.work_id,
    ):
        raise PrintableResponseIntegrityError("Page identity does not match work_ref.")
    return page


def load_printable_response_record_set(
    workspace_root: str | Path,
    work_ref: object,
    issuance_id: str,
) -> PrintableResponseRecordSet:
    """Load an issuance and all exact members in authoritative stored order."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    issuance = load_printable_response_issuance(
        workspace_root, validated_work_ref, issuance_id
    )
    pages = tuple(
        load_printable_response_page(workspace_root, validated_work_ref, page_id)
        for page_id in issuance.page_ids
    )
    try:
        return PrintableResponseRecordSet(issuance, pages)
    except PrintableResponseRecordValidationError as error:
        raise PrintableResponseIntegrityError(f"Invalid record-set membership: {error}") from error


def load_printable_response_page_context(
    workspace_root: str | Path,
    work_ref: object,
    page_id: str,
) -> PrintableResponsePageContext:
    """Resolve page meaning solely from its complete immutable record set."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    page = load_printable_response_page(workspace_root, validated_work_ref, page_id)
    record_set = load_printable_response_record_set(
        workspace_root, validated_work_ref, page.issuance_id
    )
    members = tuple(member for member in record_set.pages if member.page_id == page.page_id)
    if len(members) != 1 or members[0] != page:
        raise PrintableResponseIntegrityError(
            "Requested page does not occur exactly once in its named issuance."
        )
    return PrintableResponsePageContext(page, record_set.issuance, record_set.pages)


def _verify_source_file(path: Path, description: str) -> None:
    if not path.exists():
        raise PrintableResponsePersistenceValidationError(f"{description} not found: {path}")
    if _is_link_like(path) or not path.is_file():
        raise PrintableResponsePersistenceValidationError(
            f"{description} must be an ordinary non-link file: {path}"
        )


def _verify_creation_sources(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance: PrintableResponseIssuance,
) -> None:
    paths = quillan_work_paths(workspace_root, work_ref.class_id, work_ref.work_id)
    _verify_source_file(paths.assignment_path, "Canonical assignment")
    try:
        assignment = load_assignment_config(paths.assignment_path)
    except (AssignmentConfigError, OSError) as error:
        raise PrintableResponsePersistenceValidationError(
            f"Canonical assignment is invalid: {error}"
        ) from error
    expected_assignment = (
        issuance.assignment_id,
        issuance.assignment_snapshot.schema_version,
        issuance.assignment_snapshot.title,
        issuance.assignment_snapshot.updated_at,
    )
    actual_assignment = (
        assignment["assignment_id"],
        assignment["schema_version"],
        assignment["title"],
        assignment["updated_at"],
    )
    if actual_assignment != expected_assignment or issuance.class_id not in assignment["class_ids"]:
        raise PrintableResponsePersistenceValidationError(
            "Assignment snapshot does not match the current canonical assignment."
        )
    _verify_source_file(paths.roster_path, "Canonical class roster")
    try:
        roster = load_class_roster(workspace_root, work_ref.class_id)
    except (RosterError, OSError, ValueError) as error:
        raise PrintableResponsePersistenceValidationError(
            f"Canonical class roster is invalid: {error}"
        ) from error
    if roster.class_id != issuance.class_id:
        raise PrintableResponsePersistenceValidationError("Roster class does not match issuance.")
    matches = tuple(
        student for student in roster.students if student.student_id == issuance.student_id
    )
    if len(matches) != 1:
        raise PrintableResponsePersistenceValidationError(
            "Issuance student_id must occur exactly once in the current roster."
        )
    student = matches[0]
    snapshot = issuance.student_snapshot
    if (
        student_display_name(student), student.last_name, student.first_name, student.period
    ) != (snapshot.display_name, snapshot.last_name, snapshot.first_name, snapshot.period):
        raise PrintableResponsePersistenceValidationError(
            "Student snapshot does not match the current canonical roster."
        )


def _verify_predecessor(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance: PrintableResponseIssuance,
) -> None:
    predecessor_id = issuance.generation_context.predecessor_issuance_id
    if predecessor_id is None:
        return
    predecessor = load_printable_response_issuance(
        workspace_root, work_ref, predecessor_id
    )
    if (
        predecessor.class_id,
        predecessor.assignment_id,
        predecessor.student_id,
    ) != (issuance.class_id, issuance.assignment_id, issuance.student_id):
        raise PrintableResponsePersistenceValidationError(
            "Regeneration predecessor does not share class, assignment, and student identity."
        )
    reused: list[str] = []
    if issuance.issuance_id == predecessor.issuance_id:
        reused.append("issuance_id")
    if issuance.generation_id == predecessor.generation_id:
        reused.append("generation_id")
    if issuance.artifact_id == predecessor.artifact_id:
        reused.append("artifact_id")
    if not set(issuance.page_ids).isdisjoint(predecessor.page_ids):
        reused.append("page_ids")
    if reused:
        raise PrintableResponsePersistenceValidationError(
            "Regeneration must use fresh identities; reused: " + ", ".join(reused) + "."
        )


def _write_json_exclusive(
    path: Path, value: Mapping[str, Any]
) -> _CreatedRecord:
    data = canonical_printable_response_json(value)
    created = False
    try:
        with path.open("xb") as file:
            created = True
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError as error:
        raise PrintableResponseRecordCollisionError(
            f"Immutable record destination already exists: {path}"
        ) from error
    except OSError as error:
        if created:
            rollback_failures = _rollback_created_records(
                [_CreatedRecord(path, data)]
            )
            if rollback_failures:
                raise PrintableResponseRollbackError(
                    f"Failed write left an incompletely rolled-back record: {path}"
                ) from error
        raise
    return _CreatedRecord(path, data)


def _rollback_created_records(
    created: list[_CreatedRecord],
) -> tuple[Path, ...]:
    failures: list[Path] = []
    for record in reversed(created):
        path = record.path
        try:
            if not path.exists() and not _is_link_like(path):
                continue
            if _is_link_like(path) or (path.exists() and not path.is_file()):
                failures.append(path)
                continue
            if path.read_bytes() != record.expected_bytes:
                failures.append(path)
                continue
            path.unlink(missing_ok=True)
        except OSError:
            failures.append(path)
    return tuple(failures)


def write_printable_response_record_set(
    workspace_root: str | Path,
    work_ref: object,
    record_set: object,
) -> PersistedPrintableResponseRecordSet:
    """Exclusively commit pages first and the issuance aggregate marker last."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    try:
        validate_printable_response_record_set(record_set)
        validated_record_set = cast(PrintableResponseRecordSet, record_set)
        paths = quillan_work_paths(
            workspace_root,
            validated_work_ref.class_id,
            validated_work_ref.work_id,
        )
    except (PrintableResponseRecordValidationError, ValueError, TypeError) as error:
        raise PrintableResponsePersistenceValidationError(str(error)) from error
    if validated_work_ref != paths.work_ref:
        raise PrintableResponsePersistenceValidationError(
            "work_ref must be a canonical Quillan-owned ModuleWorkRef."
        )
    issuance = validated_record_set.issuance
    if (issuance.class_id, issuance.assignment_id) != (
        validated_work_ref.class_id,
        validated_work_ref.work_id,
    ):
        raise PrintableResponsePersistenceValidationError(
            "Record-set identity does not match work_ref."
        )
    lifecycle = issuance.lifecycle
    if lifecycle.status != "prepared" or lifecycle.revision != 1:
        raise PrintableResponsePersistenceValidationError(
            "New record sets require a prepared revision-1 lifecycle."
        )
    try:
        page_paths = tuple(
            response_page_record_path(
                workspace_root, validated_work_ref, page.page_id
            )
            for page in validated_record_set.pages
        )
        issuance_path = response_page_issuance_path(
            workspace_root, validated_work_ref, issuance.issuance_id
        )
        _preflight_directories(
            Path(workspace_root),
            (
                paths.response_pages_dir,
                paths.response_page_issuances_dir,
                paths.response_page_records_dir,
            ),
        )
        for target in (*page_paths, issuance_path):
            _preflight_exact_file(workspace_root, validated_work_ref, target)
    except (QuillanWorkPathError, PrintableResponseIntegrityError) as error:
        raise PrintableResponseIntegrityError(str(error)) from error
    _verify_predecessor(workspace_root, validated_work_ref, issuance)
    collisions = tuple(path for path in (*page_paths, issuance_path) if path.exists())
    if collisions:
        raise PrintableResponseRecordCollisionError(
            f"Immutable record destination already exists: {collisions[0]}"
        )
    _verify_creation_sources(workspace_root, validated_work_ref, issuance)
    try:
        paths.response_page_records_dir.mkdir(parents=True, exist_ok=True)
        paths.response_page_issuances_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise PrintableResponseRecordSetWriteError(
            f"Could not create response-page collection directories: {error}"
        ) from error
    created: list[_CreatedRecord] = []
    try:
        for page, path in zip(validated_record_set.pages, page_paths, strict=True):
            _preflight_exact_file(workspace_root, validated_work_ref, path)
            created.append(_write_json_exclusive(path, page.to_mapping()))
        _preflight_exact_file(workspace_root, validated_work_ref, issuance_path)
        created.append(_write_json_exclusive(issuance_path, issuance.to_mapping()))
    except Exception as error:
        rollback_failures = _rollback_created_records(created)
        if rollback_failures:
            raise PrintableResponseRollbackError(
                "Record-set write failed and rollback was incomplete: "
                + ", ".join(str(path) for path in rollback_failures)
            ) from error
        if isinstance(error, PrintableResponsePersistenceError):
            raise
        raise PrintableResponseRecordSetWriteError(
            f"Record-set write failed and current-operation files were rolled back: {error}"
        ) from error
    return PersistedPrintableResponseRecordSet(
        validated_record_set, issuance_path, page_paths
    )


def _atomic_replace_issuance(
    path: Path,
    issuance: PrintableResponseIssuance,
    *,
    expected_bytes: bytes,
) -> None:
    data = canonical_printable_response_json(issuance.to_mapping())
    temporary: Path | None = None
    failure: PrintableResponseLifecycleError | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{issuance.issuance_id}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if _is_link_like(path) or not path.is_file():
            raise PrintableResponseLifecycleError(
                "Issuance destination changed filesystem type before replacement."
            )
        if path.read_bytes() != expected_bytes:
            raise PrintableResponseRevisionConflictError(
                "Issuance changed after its revision was checked."
            )
        os.replace(temporary, path)
        temporary = None
    except PrintableResponseLifecycleError as error:
        failure = error
    except OSError as error:
        failure = PrintableResponseLifecycleError(
            f"Could not atomically replace issuance lifecycle: {error}"
        )
    if temporary is not None:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as cleanup_error:
            primary = (
                f" Primary failure: {failure}"
                if failure is not None
                else ""
            )
            combined = PrintableResponseLifecycleCleanupError(
                f"Could not remove abandoned lifecycle temporary file {temporary}: "
                f"{cleanup_error}.{primary}"
            )
            if failure is not None:
                raise combined from failure
            raise combined from cleanup_error
    if failure is not None:
        raise failure


def transition_printable_response_issuance(
    workspace_root: str | Path,
    work_ref: object,
    issuance_id: str,
    *,
    expected_revision: int,
    new_status: str,
    timestamp: datetime | str,
    reason: str | None = None,
    replacement_issuance_id: str | None = None,
) -> PrintableResponseIssuance:
    """Revision-guard and atomically persist one allowed issuance transition."""
    validated_work_ref = _validated_quillan_work_ref(work_ref)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise PrintableResponseRevisionConflictError("expected_revision must be an integer.")
    issuance, original_bytes = _load_printable_response_issuance_with_bytes(
        workspace_root, validated_work_ref, issuance_id
    )
    if issuance.lifecycle.revision != expected_revision:
        raise PrintableResponseRevisionConflictError(
            f"Expected revision {expected_revision}, found {issuance.lifecycle.revision}."
        )
    if new_status == "superseded":
        if replacement_issuance_id is None:
            raise PrintableResponseLifecycleError(
                "Supersession requires replacement_issuance_id."
            )
        replacement = load_printable_response_issuance(
            workspace_root, validated_work_ref, replacement_issuance_id
        )
        if replacement.issuance_id == issuance.issuance_id:
            raise PrintableResponseLifecycleError("An issuance cannot replace itself.")
        if replacement.lifecycle.status != "issued":
            raise PrintableResponseLifecycleError(
                "A supersession replacement must already be issued."
            )
        if (
            replacement.class_id,
            replacement.assignment_id,
            replacement.student_id,
        ) != (issuance.class_id, issuance.assignment_id, issuance.student_id):
            raise PrintableResponseLifecycleError(
                "Replacement must share class, assignment, and student identity."
            )
    try:
        lifecycle = transition_printable_response_lifecycle(
            issuance.lifecycle,
            new_status=new_status,
            timestamp=timestamp,
            reason=reason,
            replacement_issuance_id=replacement_issuance_id,
        )
        updated = replace(issuance, lifecycle=lifecycle)
    except PrintableResponseRecordValidationError as error:
        raise PrintableResponseLifecycleError(str(error)) from error
    try:
        path = response_page_issuance_path(
            workspace_root, validated_work_ref, issuance.issuance_id
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseIntegrityError(str(error)) from error
    _preflight_exact_file(workspace_root, validated_work_ref, path)
    _atomic_replace_issuance(path, updated, expected_bytes=original_bytes)
    return updated


__all__ = [
    "PersistedPrintableResponseRecordSet",
    "PrintableResponseIntegrityError",
    "PrintableResponseLifecycleCleanupError",
    "PrintableResponseLifecycleError",
    "PrintableResponseNotFoundError",
    "PrintableResponsePersistenceError",
    "PrintableResponsePersistenceValidationError",
    "PrintableResponseReadError",
    "PrintableResponseRecordCollisionError",
    "PrintableResponseRecordSetWriteError",
    "PrintableResponseRevisionConflictError",
    "PrintableResponseRollbackError",
    "canonical_printable_response_json",
    "load_printable_response_issuance",
    "load_printable_response_page",
    "load_printable_response_page_context",
    "load_printable_response_record_set",
    "response_page_issuance_path",
    "response_page_record_path",
    "transition_printable_response_issuance",
    "write_printable_response_record_set",
]

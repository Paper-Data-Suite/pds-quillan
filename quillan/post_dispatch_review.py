"""Append-only, durability-aware Quillan post-dispatch review records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast
from uuid import uuid4

from pds_core.identifiers import validate_identifier
from pds_core.routing_models import ModuleWorkRef

from quillan.atomic_record_io import (
    AtomicRecordConcurrencyError,
    AtomicRecordDurabilityError,
    AtomicRecordError,
    create_exclusive_record,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.record_context import canonical_workspace_root
from quillan.scan_review_resolution import QuillanReviewItem, discover_scan_review_items
from quillan.work_paths import (
    QuillanWorkPathError,
    post_dispatch_review_dir,
    post_dispatch_review_path,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
    response_page_observation_path,
    submission_manifest_path,
)

POST_DISPATCH_SCHEMA_VERSION: Final = "1"
POST_DISPATCH_RECORD_TYPE: Final = "post_dispatch_review_occurrence"
POST_DISPATCH_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "observation_persistence",
        "routed_evidence_persistence",
        "submission_assembly",
        "mixed_issuance",
        "manifest_conflict",
        "post_dispatch_integrity",
    }
)


class PostDispatchReviewError(RuntimeError):
    """Raised when a post-dispatch occurrence is invalid or durability is uncertain."""

    def __init__(
        self,
        message: str,
        *,
        possibly_durable_path: Path | None = None,
        possible_lock_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.possibly_durable_path = possibly_durable_path
        self.possible_lock_path = possible_lock_path


class QuillanReviewSource(str, Enum):
    CORE_ROUTING = "core_routing"
    POST_DISPATCH = "post_dispatch"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class PostDispatchReviewOccurrence:
    failure_id: str
    category: str
    stage: str
    created_at: str
    class_id: str
    assignment_id: str
    student_id: str | None
    issuance_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_scan_ids: tuple[str, ...]
    source_page_numbers: tuple[int, ...]
    possible_observation_paths: tuple[str, ...]
    possible_evidence_paths: tuple[str, ...]
    possible_manifest_paths: tuple[str, ...]
    failure_message: str
    module_details: Mapping[str, object]

    def __post_init__(self) -> None:
        _identifier(self.failure_id, "failure_id")
        _identifier(self.class_id, "class_id")
        _identifier(self.assignment_id, "assignment_id")
        if self.student_id is not None:
            _identifier(self.student_id, "student_id")
        if (
            type(self.category) is not str
            or self.category not in POST_DISPATCH_CATEGORIES
        ):
            raise PostDispatchReviewError("Occurrence category is invalid.")
        if (
            type(self.stage) is not str
            or not self.stage
            or self.stage != self.stage.strip()
        ):
            raise PostDispatchReviewError("Occurrence stage must be nonempty text.")
        if (
            type(self.failure_message) is not str
            or not self.failure_message
            or self.failure_message != self.failure_message.strip()
        ):
            raise PostDispatchReviewError(
                "Occurrence failure_message must be nonempty text."
            )
        _timestamp(self.created_at)
        for field in (
            "issuance_ids",
            "page_ids",
            "route_ids",
            "observation_ids",
            "source_scan_ids",
        ):
            values = getattr(self, field)
            _identity_tuple(values, field)
        _positive_integer_tuple(self.source_page_numbers, "source_page_numbers")
        for field in (
            "possible_observation_paths",
            "possible_evidence_paths",
            "possible_manifest_paths",
        ):
            values = getattr(self, field)
            if type(values) is not tuple or any(
                type(item) is not str or not item for item in values
            ):
                raise PostDispatchReviewError(f"{field} contains invalid path text.")
            if values != tuple(sorted(set(values))):
                raise PostDispatchReviewError(
                    f"{field} must be a deterministic unique text tuple."
                )
        frozen = _freeze_json_mapping(self.module_details)
        object.__setattr__(self, "module_details", frozen)

    @property
    def issuance_id(self) -> str | None:
        return _sole(self.issuance_ids)

    @property
    def page_id(self) -> str | None:
        return _sole(self.page_ids)

    @property
    def route_id(self) -> str | None:
        return _sole(self.route_ids)

    @property
    def observation_id(self) -> str | None:
        return _sole(self.observation_ids)

    @property
    def source_scan_id(self) -> str | None:
        return _sole(self.source_scan_ids)

    @property
    def source_page_number(self) -> int | None:
        return _sole(self.source_page_numbers)

    @property
    def possible_observation_path(self) -> str | None:
        return _sole(self.possible_observation_paths)

    @property
    def possible_evidence_path(self) -> str | None:
        return _sole(self.possible_evidence_paths)

    @property
    def possible_manifest_path(self) -> str | None:
        return _sole(self.possible_manifest_paths)


@dataclass(frozen=True, slots=True)
class PersistedPostDispatchReviewOccurrence:
    workspace_root: Path
    work_ref: ModuleWorkRef
    occurrence: PostDispatchReviewOccurrence
    path: Path
    relative_path: str

    def __post_init__(self) -> None:
        if type(self.occurrence) is not PostDispatchReviewOccurrence:
            raise PostDispatchReviewError("Persisted occurrence has the wrong type.")
        if type(self.workspace_root) is not type(Path()):
            raise PostDispatchReviewError(
                "Persisted occurrence workspace_root must be an exact Path."
            )
        try:
            canonical_root = canonical_workspace_root(self.workspace_root)
        except (OSError, ValueError) as error:
            raise PostDispatchReviewError(str(error)) from error
        if canonical_root != self.workspace_root:
            raise PostDispatchReviewError(
                "Persisted occurrence workspace_root must be canonical."
            )
        if type(self.work_ref) is not ModuleWorkRef:
            raise PostDispatchReviewError(
                "Persisted occurrence work_ref must be an exact ModuleWorkRef."
            )
        try:
            canonical_ref = quillan_work_ref(
                self.occurrence.class_id,
                self.occurrence.assignment_id,
            )
        except (AttributeError, ValueError) as error:
            raise PostDispatchReviewError(str(error)) from error
        if self.work_ref != canonical_ref:
            raise PostDispatchReviewError(
                "Persisted occurrence work_ref disagrees with occurrence identity."
            )
        if type(self.path) is not type(Path()) or not self.path.is_absolute():
            raise PostDispatchReviewError("Persisted occurrence path must be absolute.")
        expected_path = post_dispatch_review_path(
            self.workspace_root,
            self.work_ref,
            self.occurrence.failure_id,
        )
        if self.path != expected_path:
            raise PostDispatchReviewError(
                "Persisted occurrence path is not its exact canonical destination."
            )
        _relative_posix(self.relative_path)
        if self.relative_path != self.path.relative_to(self.workspace_root).as_posix():
            raise PostDispatchReviewError(
                "Persisted occurrence relative_path is not exact."
            )
        try:
            preflight_work_file_destination(
                self.workspace_root,
                self.work_ref,
                Path("scans") / "review" / "post_dispatch" / self.path.name,
            )
        except QuillanWorkPathError as error:
            raise PostDispatchReviewError(str(error)) from error


@dataclass(frozen=True, slots=True)
class PostDispatchReviewDiscovery:
    items: tuple[PersistedPostDispatchReviewOccurrence, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        _typed_tuple(self.items, PersistedPostDispatchReviewOccurrence, "items")
        _text_tuple(self.warnings, "warnings", unique=False)
        identities = tuple(item.occurrence.failure_id for item in self.items)
        if len(set(identities)) != len(identities):
            raise PostDispatchReviewError("Discovery contains duplicate failure IDs.")
        if self.items != tuple(
            sorted(
                self.items,
                key=lambda item: (
                    item.occurrence.created_at,
                    item.occurrence.failure_id,
                ),
            )
        ):
            raise PostDispatchReviewError("Discovery items are not deterministic.")


@dataclass(frozen=True, slots=True)
class QuillanOwnedReviewDiscovery:
    items: tuple[QuillanReviewItem | PersistedPostDispatchReviewOccurrence, ...]
    core_warnings: tuple[str, ...]
    post_dispatch_warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.items) is not tuple or any(
            type(item) not in {QuillanReviewItem, PersistedPostDispatchReviewOccurrence}
            for item in self.items
        ):
            raise PostDispatchReviewError("Combined review items have invalid types.")
        _text_tuple(self.core_warnings, "core_warnings", unique=False)
        _text_tuple(
            self.post_dispatch_warnings,
            "post_dispatch_warnings",
            unique=False,
        )


def create_post_dispatch_review_occurrence(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    *,
    category: str,
    stage: str,
    failure_message: str,
    student_id: str | None = None,
    issuance_id: str | None = None,
    page_id: str | None = None,
    route_id: str | None = None,
    observation_id: str | None = None,
    source_scan_id: str | None = None,
    source_page_number: int | None = None,
    issuance_ids: tuple[str, ...] = (),
    page_ids: tuple[str, ...] = (),
    route_ids: tuple[str, ...] = (),
    observation_ids: tuple[str, ...] = (),
    source_scan_ids: tuple[str, ...] = (),
    source_page_numbers: tuple[int, ...] = (),
    possible_observation_path: str | Path | None = None,
    possible_evidence_path: str | Path | None = None,
    possible_manifest_path: str | Path | None = None,
    possible_observation_paths: tuple[str | Path, ...] = (),
    possible_evidence_paths: tuple[str | Path, ...] = (),
    possible_manifest_paths: tuple[str | Path, ...] = (),
    module_details: Mapping[str, object] | None = None,
    created_at: datetime | str | None = None,
) -> PersistedPostDispatchReviewOccurrence:
    """Append one occurrence beneath a strictly preflighted affected work root."""
    root = canonical_workspace_root(workspace_root)
    if type(work_ref) is not ModuleWorkRef:
        raise PostDispatchReviewError("work_ref must be an exact ModuleWorkRef.")
    canonical_ref = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    if work_ref != canonical_ref:
        raise PostDispatchReviewError("work_ref must be an exact Quillan work reference.")
    if student_id is not None:
        validate_identifier(student_id, "student_id")
    all_issuance_ids = _merge_identity(issuance_ids, issuance_id, "issuance_ids")
    all_page_ids = _merge_identity(page_ids, page_id, "page_ids")
    all_route_ids = _merge_identity(route_ids, route_id, "route_ids")
    all_observation_ids = _merge_identity(
        observation_ids, observation_id, "observation_ids"
    )
    all_source_scan_ids = _merge_identity(
        source_scan_ids, source_scan_id, "source_scan_ids"
    )
    all_source_page_numbers = _merge_numbers(
        source_page_numbers, source_page_number
    )
    observation_values = _merge_paths(
        possible_observation_paths, possible_observation_path
    )
    evidence_values = _merge_paths(possible_evidence_paths, possible_evidence_path)
    manifest_values = _merge_paths(possible_manifest_paths, possible_manifest_path)
    normalized_paths = {
        "possible_observation_paths": _possible_paths(
            root,
            work_ref,
            observation_values,
            kind="observation",
            student_id=student_id,
            observation_ids=all_observation_ids,
        ),
        "possible_evidence_paths": _possible_paths(
            root,
            work_ref,
            evidence_values,
            kind="evidence",
            student_id=student_id,
            observation_ids=all_observation_ids,
        ),
        "possible_manifest_paths": _possible_paths(
            root,
            work_ref,
            manifest_values,
            kind="manifest",
            student_id=student_id,
            observation_ids=all_observation_ids,
        ),
    }
    timestamp = _timestamp(created_at)
    directory = _prepare_directory(root, work_ref)
    for _ in range(8):
        failure_id = f"failure_{uuid4().hex}"
        occurrence = PostDispatchReviewOccurrence(
            failure_id=failure_id,
            category=category,
            stage=stage.strip() if isinstance(stage, str) else stage,
            created_at=timestamp,
            class_id=work_ref.class_id,
            assignment_id=work_ref.work_id,
            student_id=student_id,
            failure_message=(
                failure_message.strip()
                if isinstance(failure_message, str)
                else failure_message
            ),
            module_details={} if module_details is None else module_details,
            issuance_ids=all_issuance_ids,
            page_ids=all_page_ids,
            route_ids=all_route_ids,
            observation_ids=all_observation_ids,
            source_scan_ids=all_source_scan_ids,
            source_page_numbers=all_source_page_numbers,
            **normalized_paths,
        )
        target = post_dispatch_review_path(root, work_ref, failure_id)
        if os.path.lexists(target):
            continue
        return _write_occurrence(root, work_ref, directory, occurrence)
    raise PostDispatchReviewError("Could not allocate a unique occurrence ID.")


def discover_post_dispatch_review_occurrences(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> PostDispatchReviewDiscovery:
    root = canonical_workspace_root(workspace_root)
    canonical_ref = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    if type(work_ref) is not ModuleWorkRef or work_ref != canonical_ref:
        raise PostDispatchReviewError("work_ref must be an exact Quillan work reference.")
    directory = post_dispatch_review_dir(root, work_ref)
    if not os.path.lexists(directory):
        preflight_work_directory_destination(
            root, work_ref, Path("scans") / "review" / "post_dispatch"
        )
        return PostDispatchReviewDiscovery((), ())
    try:
        preflight_work_directory_destination(
            root, work_ref, Path("scans") / "review" / "post_dispatch"
        )
    except QuillanWorkPathError as error:
        return PostDispatchReviewDiscovery((), (f"Unsafe review directory: {error}",))
    items: list[PersistedPostDispatchReviewOccurrence] = []
    warnings: list[str] = []
    try:
        children = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    except OSError as error:
        return PostDispatchReviewDiscovery((), (f"Could not inspect review directory: {error}",))
    seen: set[str] = set()
    for path in children:
        if path.suffix != ".json":
            continue
        try:
            preflight_work_file_destination(
                root,
                work_ref,
                Path("scans") / "review" / "post_dispatch" / path.name,
            )
            data = path.read_bytes()
            occurrence = _occurrence_from_bytes(data, root, work_ref)
            if path != post_dispatch_review_path(root, work_ref, occurrence.failure_id):
                raise PostDispatchReviewError("filename and failure_id disagree")
            if occurrence.failure_id in seen:
                raise PostDispatchReviewError("duplicate failure_id")
            seen.add(occurrence.failure_id)
            items.append(
                PersistedPostDispatchReviewOccurrence(
                    root,
                    work_ref,
                    occurrence,
                    path,
                    path.relative_to(root).as_posix(),
                )
            )
        except (
            PostDispatchReviewError,
            QuillanWorkPathError,
            OSError,
            UnicodeError,
            ValueError,
        ) as error:
            warnings.append(f"Skipped malformed occurrence {path.name}: {error}")
    items.sort(key=lambda item: (item.occurrence.created_at, item.occurrence.failure_id))
    return PostDispatchReviewDiscovery(tuple(items), tuple(warnings))


def discover_quillan_owned_review_items(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    *,
    source: QuillanReviewSource = QuillanReviewSource.BOTH,
    include_resolved_core: bool = False,
) -> QuillanOwnedReviewDiscovery:
    if type(source) is not QuillanReviewSource:
        raise PostDispatchReviewError("source must be a QuillanReviewSource.")
    core_items: tuple[QuillanReviewItem, ...] = ()
    core_warnings: tuple[str, ...] = ()
    post_items: tuple[PersistedPostDispatchReviewOccurrence, ...] = ()
    post_warnings: tuple[str, ...] = ()
    if source in {QuillanReviewSource.CORE_ROUTING, QuillanReviewSource.BOTH}:
        core = discover_scan_review_items(
            workspace_root,
            include_resolved=include_resolved_core,
            class_id=work_ref.class_id,
            assignment_id=work_ref.work_id,
        )
        core_items, core_warnings = core.items, core.warnings
    if source in {QuillanReviewSource.POST_DISPATCH, QuillanReviewSource.BOTH}:
        post = discover_post_dispatch_review_occurrences(workspace_root, work_ref)
        post_items, post_warnings = post.items, post.warnings
    return QuillanOwnedReviewDiscovery(
        (*core_items, *post_items), core_warnings, post_warnings
    )


def _prepare_directory(root: Path, work_ref: ModuleWorkRef) -> Path:
    try:
        directory = preflight_work_directory_destination(
            root, work_ref, Path("scans") / "review" / "post_dispatch"
        )
        directory.mkdir(parents=True, exist_ok=True)
        preflight_work_directory_destination(
            root, work_ref, Path("scans") / "review" / "post_dispatch"
        )
    except (OSError, QuillanWorkPathError) as error:
        raise PostDispatchReviewError(str(error)) from error
    return directory


def _write_occurrence(
    root: Path,
    work_ref: ModuleWorkRef,
    directory: Path,
    occurrence: PostDispatchReviewOccurrence,
) -> PersistedPostDispatchReviewOccurrence:
    path = post_dispatch_review_path(root, work_ref, occurrence.failure_id)
    data = _occurrence_bytes(occurrence)

    def preflight() -> None:
        if canonical_workspace_root(root) != root:
            raise PostDispatchReviewError("Workspace root identity changed.")
        expected_directory = preflight_work_directory_destination(
            root, work_ref, Path("scans") / "review" / "post_dispatch"
        )
        if expected_directory != directory:
            raise PostDispatchReviewError("Review directory identity changed.")
        preflight_work_file_destination(
            root,
            work_ref,
            Path("scans") / "review" / "post_dispatch" / path.name,
        )

    try:
        create_exclusive_record(
            path,
            data,
            preflight=preflight,
            verify_bytes=lambda loaded: _verify_occurrence_bytes(
                loaded, root, work_ref, occurrence
            ),
        )
    except AtomicRecordConcurrencyError as error:
        raise PostDispatchReviewError(f"Occurrence collision: {error}") from error
    except AtomicRecordDurabilityError as error:
        raise PostDispatchReviewError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, OSError, QuillanWorkPathError) as error:
        raise PostDispatchReviewError(f"Could not persist occurrence: {error}") from error
    return PersistedPostDispatchReviewOccurrence(
        root,
        work_ref,
        occurrence,
        path,
        path.relative_to(root).as_posix(),
    )


def _occurrence_bytes(occurrence: PostDispatchReviewOccurrence) -> bytes:
    value = {
        "schema_version": POST_DISPATCH_SCHEMA_VERSION,
        "record_type": POST_DISPATCH_RECORD_TYPE,
        "module_id": QUILLAN_MODULE_ID,
        **{
            field: _thaw(getattr(occurrence, field))
            for field in occurrence.__dataclass_fields__
        },
    }
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _verify_occurrence_bytes(
    data: bytes,
    root: Path,
    work_ref: ModuleWorkRef,
    expected: PostDispatchReviewOccurrence,
) -> None:
    if _occurrence_from_bytes(data, root, work_ref) != expected:
        raise PostDispatchReviewError(
            "Reloaded occurrence differs from the committed model."
        )


def _occurrence_from_bytes(
    data: bytes, root: Path, work_ref: ModuleWorkRef
) -> PostDispatchReviewOccurrence:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PostDispatchReviewError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise PostDispatchReviewError(f"Invalid JSON constant: {value}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PostDispatchReviewError(f"Occurrence is not strict JSON: {error}") from error
    if not isinstance(value, dict):
        raise PostDispatchReviewError("Occurrence must be an object.")
    fixed = {"schema_version", "record_type", "module_id"}
    fields = set(PostDispatchReviewOccurrence.__dataclass_fields__)
    if set(value) != fixed | fields:
        raise PostDispatchReviewError("Occurrence fields are not exact.")
    if (
        value["schema_version"] != POST_DISPATCH_SCHEMA_VERSION
        or value["record_type"] != POST_DISPATCH_RECORD_TYPE
        or value["module_id"] != QUILLAN_MODULE_ID
        or value["class_id"] != work_ref.class_id
        or value["assignment_id"] != work_ref.work_id
    ):
        raise PostDispatchReviewError("Occurrence fixed identity is invalid.")
    tuple_fields = {
        "issuance_ids",
        "page_ids",
        "route_ids",
        "observation_ids",
        "source_scan_ids",
        "source_page_numbers",
        "possible_observation_paths",
        "possible_evidence_paths",
        "possible_manifest_paths",
    }
    for field in tuple_fields:
        if not isinstance(value[field], list):
            raise PostDispatchReviewError(f"Occurrence {field} must be an array.")
    occurrence = PostDispatchReviewOccurrence(
        failure_id=cast(str, value["failure_id"]),
        category=cast(str, value["category"]),
        stage=cast(str, value["stage"]),
        created_at=cast(str, value["created_at"]),
        class_id=cast(str, value["class_id"]),
        assignment_id=cast(str, value["assignment_id"]),
        student_id=cast(str | None, value["student_id"]),
        issuance_ids=tuple(cast(list[str], value["issuance_ids"])),
        page_ids=tuple(cast(list[str], value["page_ids"])),
        route_ids=tuple(cast(list[str], value["route_ids"])),
        observation_ids=tuple(cast(list[str], value["observation_ids"])),
        source_scan_ids=tuple(cast(list[str], value["source_scan_ids"])),
        source_page_numbers=tuple(
            cast(list[int], value["source_page_numbers"])
        ),
        possible_observation_paths=tuple(
            cast(list[str], value["possible_observation_paths"])
        ),
        possible_evidence_paths=tuple(
            cast(list[str], value["possible_evidence_paths"])
        ),
        possible_manifest_paths=tuple(
            cast(list[str], value["possible_manifest_paths"])
        ),
        failure_message=cast(str, value["failure_message"]),
        module_details=cast(Mapping[str, object], value["module_details"]),
    )
    for item in occurrence.possible_observation_paths:
        _possible_paths(root, work_ref, (item,), kind="observation", student_id=occurrence.student_id, observation_ids=occurrence.observation_ids)
    for item in occurrence.possible_evidence_paths:
        _possible_paths(root, work_ref, (item,), kind="evidence", student_id=occurrence.student_id, observation_ids=occurrence.observation_ids)
    for item in occurrence.possible_manifest_paths:
        _possible_paths(root, work_ref, (item,), kind="manifest", student_id=occurrence.student_id, observation_ids=occurrence.observation_ids)
    return occurrence


def _possible_paths(
    root: Path,
    work_ref: ModuleWorkRef,
    values: tuple[str | Path, ...],
    *,
    kind: str,
    student_id: str | None,
    observation_ids: object,
) -> tuple[str, ...]:
    normalized: list[str] = []
    work_root = quillan_work_paths(root, work_ref.class_id, work_ref.work_id).work_root
    for value in values:
        if not isinstance(value, (str, Path)):
            raise PostDispatchReviewError("Possible durable path has the wrong type.")
        path = Path(value)
        absolute = path if path.is_absolute() else root / path
        absolute = Path(os.path.abspath(absolute))
        try:
            work_relative = absolute.relative_to(work_root)
            workspace_relative = absolute.relative_to(root).as_posix()
        except ValueError as error:
            raise PostDispatchReviewError(
                "Possible durable paths must remain in the affected Quillan work root."
            ) from error
        try:
            preflight_work_file_destination(root, work_ref, work_relative)
        except QuillanWorkPathError as error:
            raise PostDispatchReviewError(str(error)) from error
        if kind == "observation":
            if not work_relative.as_posix().startswith("scans/observations/"):
                raise PostDispatchReviewError("Possible observation path is noncanonical.")
            ids = cast(tuple[str, ...], observation_ids)
            if len(ids) == 1 and absolute != response_page_observation_path(
                root, work_ref, ids[0]
            ):
                raise PostDispatchReviewError(
                    "Possible observation path disagrees with observation identity."
                )
        elif kind == "evidence":
            if not work_relative.as_posix().startswith("scans/evidence/"):
                raise PostDispatchReviewError("Possible evidence path is noncanonical.")
            if student_id is not None and f"response_{student_id}_" not in absolute.name:
                raise PostDispatchReviewError(
                    "Possible evidence path disagrees with student identity."
                )
        elif kind == "manifest":
            if student_id is None or absolute != submission_manifest_path(
                root, work_ref, student_id
            ):
                raise PostDispatchReviewError("Possible manifest path is noncanonical.")
        else:
            raise PostDispatchReviewError("Unknown possible-path class.")
        normalized.append(workspace_relative)
    return tuple(sorted(set(normalized)))


def _merge_identity(
    values: tuple[str, ...], value: str | None, field: str
) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise PostDispatchReviewError(f"{field} must be a tuple.")
    combined = values + (() if value is None else (value,))
    if any(type(item) is not str for item in combined):
        raise PostDispatchReviewError(f"{field} contains non-text identity.")
    result = tuple(sorted(set(combined)))
    _identity_tuple(result, field)
    return result


def _merge_numbers(values: tuple[int, ...], value: int | None) -> tuple[int, ...]:
    if type(values) is not tuple:
        raise PostDispatchReviewError("source_page_numbers must be a tuple.")
    combined = values + (() if value is None else (value,))
    if any(type(item) is not int for item in combined):
        raise PostDispatchReviewError(
            "source_page_numbers must contain exact integers."
        )
    result = tuple(sorted(set(combined)))
    _positive_integer_tuple(result, "source_page_numbers")
    return result


def _merge_paths(
    values: tuple[str | Path, ...], value: str | Path | None
) -> tuple[str | Path, ...]:
    if type(values) is not tuple:
        raise PostDispatchReviewError("Possible durable paths must be tuples.")
    return values + (() if value is None else (value,))


def _identity_tuple(values: object, field: str) -> None:
    if type(values) is not tuple:
        raise PostDispatchReviewError(f"{field} must be an exact tuple.")
    for value in values:
        if type(value) is not str:
            raise PostDispatchReviewError(f"{field} contains non-text identity.")
        _identifier(value, field.removesuffix("s"))
    if values != tuple(sorted(set(values))):
        raise PostDispatchReviewError(f"{field} must be deterministic and unique.")


def _positive_integer_tuple(values: object, field: str) -> None:
    if type(values) is not tuple or any(
        type(value) is not int or value < 1 for value in values
    ):
        raise PostDispatchReviewError(f"{field} must contain positive integers.")
    if values != tuple(sorted(set(values))):
        raise PostDispatchReviewError(f"{field} must be deterministic and unique.")


def _identifier(value: object, field: str) -> None:
    if type(value) is not str:
        raise PostDispatchReviewError(f"{field} must be exact identifier text.")
    try:
        validate_identifier(value, field)
    except ValueError as error:
        raise PostDispatchReviewError(str(error)) from error


def _timestamp(value: datetime | str | None) -> str:
    candidate: datetime | str = datetime.now(timezone.utc) if value is None else value
    if isinstance(candidate, datetime):
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise PostDispatchReviewError("created_at must be timezone-aware.")
        return candidate.isoformat(timespec="microseconds")
    if type(candidate) is not str:
        raise PostDispatchReviewError("created_at must be a datetime or string.")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise PostDispatchReviewError("created_at must be ISO 8601 text.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PostDispatchReviewError("created_at must be timezone-aware.")
    return candidate


def _freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PostDispatchReviewError("module_details must be an object.")
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if type(key) is not str:
            raise PostDispatchReviewError(
                "module_details keys must be exact strings."
            )
        if key in frozen:
            raise PostDispatchReviewError(f"Duplicate module_details key: {key}")
        frozen[key] = _freeze(item)
    return MappingProxyType(frozen)


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_json_mapping(cast(Mapping[str, object], value))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or type(value) in {str, int, float, bool}:
        if type(value) is float and (value != value or abs(value) == float("inf")):
            raise PostDispatchReviewError("module_details must be strict JSON.")
        return value
    raise PostDispatchReviewError("module_details must be strict JSON.")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _relative_posix(value: str) -> None:
    if type(value) is not str or not value or "\\" in value:
        raise PostDispatchReviewError("relative_path is not canonical POSIX text.")
    path = Path(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise PostDispatchReviewError("relative_path is not canonical POSIX text.")


def _typed_tuple(values: object, expected: type[object], field: str) -> None:
    if type(values) is not tuple or any(type(item) is not expected for item in values):
        raise PostDispatchReviewError(f"{field} has invalid runtime types.")


def _text_tuple(values: object, field: str, *, unique: bool) -> None:
    if type(values) is not tuple or any(type(item) is not str for item in values):
        raise PostDispatchReviewError(f"{field} must be an exact text tuple.")
    if unique and values != tuple(sorted(set(values))):
        raise PostDispatchReviewError(f"{field} must be deterministic and unique.")


def _sole(values: tuple[Any, ...]) -> Any | None:
    return values[0] if len(values) == 1 else None


__all__ = [
    "POST_DISPATCH_CATEGORIES",
    "POST_DISPATCH_RECORD_TYPE",
    "POST_DISPATCH_SCHEMA_VERSION",
    "PersistedPostDispatchReviewOccurrence",
    "PostDispatchReviewDiscovery",
    "PostDispatchReviewError",
    "PostDispatchReviewOccurrence",
    "QuillanOwnedReviewDiscovery",
    "QuillanReviewSource",
    "create_post_dispatch_review_occurrence",
    "discover_quillan_owned_review_items",
    "discover_post_dispatch_review_occurrences",
]

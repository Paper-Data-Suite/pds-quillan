"""Strict immutable records for successful Quillan page observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any, Final, TypeAlias, cast
import unicodedata

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.routing_models import ModuleWorkRef
from pds_core.scan_retention import RetainedSourceScan

from quillan.module_errors import (
    QuillanObservationDiscoveryError,
    QuillanObservationValidationError,
    QuillanRetainedSourceError,
    QuillanRoutedEvidenceIntegrityError,
    QuillanRoutedEvidenceMissingError,
    QuillanRoutedEvidencePathError,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.printable_response_records import (
    page_role_for_logical_page,
    validate_artifact_id,
    validate_generation_id,
    validate_issuance_id,
    validate_page_id,
)
from quillan.printable_response_routes import validate_route_id
from quillan.routed_evidence import verify_contextual_routed_page_evidence
from quillan.retained_source import validate_quillan_retained_source
from quillan.retained_source_provenance import (
    validate_serialized_core_retention_event_consistency,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_ref,
    response_page_observation_path,
    response_page_observations_dir,
    routed_evidence_path,
)

OBSERVATION_SCHEMA_VERSION: Final[str] = "1"
OBSERVATION_RECORD_TYPE: Final[str] = "response_page_observation"
OBSERVATION_ID_DOMAIN: Final[str] = "quillan-response-page-observation-v1"
ROUTED_EVIDENCE_KINDS: Final[frozenset[str]] = frozenset(
    {"retained_image_copy", "rendered_pdf_page_png"}
)
_OBSERVATION_ID = re.compile(r"^obs_[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)


def validate_observation_id(value: object) -> str:
    """Validate one deterministic observation identifier."""
    if not isinstance(value, str) or _OBSERVATION_ID.fullmatch(value) is None:
        raise QuillanObservationValidationError(
            "observation_id must be obs_ followed by 32 lowercase hexadecimal characters."
        )
    return value


def derive_observation_id(
    source_scan_id: str,
    source_page_number: int,
    route_id: str,
    page_id: str,
) -> str:
    """Derive the stable identity of one exact physical page observation."""
    _identifier(source_scan_id, "source_scan_id")
    _positive_integer(source_page_number, "source_page_number")
    validate_route_id(route_id)
    validate_page_id(page_id)
    key = "\n".join(
        (
            OBSERVATION_ID_DOMAIN,
            source_scan_id,
            str(source_page_number),
            route_id,
            page_id,
        )
    ).encode("utf-8")
    return f"obs_{hashlib.sha256(key).hexdigest()[:32]}"


generate_observation_id = derive_observation_id


@dataclass(frozen=True, slots=True)
class QuillanResponsePageObservation:
    """One immutable link from a Core-retained page to routed evidence."""

    schema_version: str
    observation_id: str
    record_type: str
    module_id: str
    created_at: str
    class_id: str
    assignment_id: str
    student_id: str
    generation_id: str
    artifact_id: str
    issuance_id: str
    page_id: str
    route_id: str
    logical_page: int
    total_pages: int
    page_role: str
    source_scan_id: str
    source_filename: str
    source_page_number: int
    retained_source_path: str
    source_sha256: str
    intake_timestamp: str
    intake_date: str
    routed_evidence_path: str
    routed_evidence_sha256: str
    routed_evidence_size_bytes: int
    routed_evidence_kind: str
    module_details: Mapping[str, FrozenJsonValue]

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVATION_SCHEMA_VERSION:
            raise QuillanObservationValidationError(
                "Unsupported observation schema_version."
            )
        if self.record_type != OBSERVATION_RECORD_TYPE:
            raise QuillanObservationValidationError("Invalid observation record_type.")
        if self.module_id != QUILLAN_MODULE_ID:
            raise QuillanObservationValidationError("Invalid observation module_id.")
        _timestamp(self.created_at, "created_at")
        for field_name in ("class_id", "assignment_id", "student_id"):
            _identifier(getattr(self, field_name), field_name)
        validate_generation_id(self.generation_id)
        validate_artifact_id(self.artifact_id)
        validate_issuance_id(self.issuance_id)
        validate_page_id(self.page_id)
        validate_route_id(self.route_id)
        logical_page = _positive_integer(self.logical_page, "logical_page")
        total_pages = _positive_integer(self.total_pages, "total_pages")
        if logical_page > total_pages:
            raise QuillanObservationValidationError(
                "logical_page must not exceed total_pages."
            )
        if self.page_role != page_role_for_logical_page(logical_page):
            raise QuillanObservationValidationError(
                "page_role contradicts logical_page."
            )
        _identifier(self.source_scan_id, "source_scan_id")
        _safe_filename(self.source_filename, "source_filename")
        _positive_integer(self.source_page_number, "source_page_number")
        _sha256(self.source_sha256, "source_sha256")
        _timestamp(self.intake_timestamp, "intake_timestamp")
        _date(self.intake_date, "intake_date")
        if self.created_at != self.intake_timestamp:
            raise QuillanObservationValidationError(
                "created_at must equal the stable intake_timestamp."
            )
        try:
            validate_serialized_core_retention_event_consistency(
                source_scan_id=self.source_scan_id,
                source_filename=self.source_filename,
                source_sha256=self.source_sha256,
                retained_source_relative_path=self.retained_source_path,
                intake_timestamp=self.intake_timestamp,
                intake_date=self.intake_date,
            )
        except ValueError as error:
            raise QuillanObservationValidationError(
                f"Observation retained provenance is inconsistent: {error}"
            ) from error
        _sha256(self.routed_evidence_sha256, "routed_evidence_sha256")
        _positive_integer(self.routed_evidence_size_bytes, "routed_evidence_size_bytes")
        if self.routed_evidence_kind not in ROUTED_EVIDENCE_KINDS:
            raise QuillanObservationValidationError("Unsupported routed_evidence_kind.")
        routed = _relative_posix_path(self.routed_evidence_path, "routed_evidence_path")
        expected_prefix = (
            "classes",
            self.class_id,
            "modules",
            QUILLAN_MODULE_ID,
            "work",
            self.assignment_id,
            "scans",
            "evidence",
            self.issuance_id,
        )
        if routed.parts[: len(expected_prefix)] != expected_prefix:
            raise QuillanObservationValidationError(
                "routed_evidence_path is not nested beneath the exact issuance directory."
            )
        if len(routed.parts) != len(expected_prefix) + 1:
            raise QuillanObservationValidationError(
                "routed_evidence_path has the wrong shape."
            )
        if self.observation_id not in routed.name:
            raise QuillanObservationValidationError(
                "Routed evidence filename must contain observation_id."
            )
        suffix = routed.suffix.lower()
        if self.routed_evidence_kind == "rendered_pdf_page_png" and suffix != ".png":
            raise QuillanObservationValidationError(
                "Rendered PDF evidence must be PNG."
            )
        if self.routed_evidence_kind == "retained_image_copy" and suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
        }:
            raise QuillanObservationValidationError(
                "Retained image evidence must preserve a supported image extension."
            )
        expected_id = derive_observation_id(
            self.source_scan_id,
            self.source_page_number,
            self.route_id,
            self.page_id,
        )
        if validate_observation_id(self.observation_id) != expected_id:
            raise QuillanObservationValidationError(
                "observation_id contradicts immutable observation identity."
            )
        frozen = _freeze_json_mapping(self.module_details, "module_details")
        object.__setattr__(self, "module_details", frozen)


def response_page_observation_to_mapping(
    observation: object,
) -> dict[str, JsonValue]:
    """Convert an exact observation model to its strict JSON mapping."""
    if type(observation) is not QuillanResponsePageObservation:
        raise QuillanObservationValidationError(
            "observation must be an exact QuillanResponsePageObservation."
        )
    result: dict[str, JsonValue] = {}
    for model_field in fields(QuillanResponsePageObservation):
        value = getattr(observation, model_field.name)
        result[model_field.name] = cast(JsonValue, _thaw_json(value))
    return result


def response_page_observation_from_mapping(
    value: object,
) -> QuillanResponsePageObservation:
    """Construct one observation from an exact-key JSON mapping."""
    if not isinstance(value, Mapping):
        raise QuillanObservationValidationError("observation must be an object.")
    expected = {item.name for item in fields(QuillanResponsePageObservation)}
    actual = set(value)
    if any(not isinstance(key, str) for key in value):
        raise QuillanObservationValidationError("observation keys must be strings.")
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing fields: " + ", ".join(missing))
        if unknown:
            details.append("unknown fields: " + ", ".join(unknown))
        raise QuillanObservationValidationError(
            "Invalid observation: " + "; ".join(details)
        )
    arguments = cast(dict[str, Any], {key: value[key] for key in expected})
    return QuillanResponsePageObservation(**arguments)


def canonical_response_page_observation_json(observation: object) -> bytes:
    """Serialize an observation deterministically as UTF-8 JSON."""
    mapping = response_page_observation_to_mapping(observation)
    return (
        json.dumps(
            mapping,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def load_response_page_observation(path: str | Path) -> QuillanResponsePageObservation:
    """Strictly load one ordinary non-link observation file."""
    if type(path) is not str and not isinstance(path, Path):
        raise QuillanObservationValidationError(
            "observation path must be an actual str or Path."
        )
    observation_path = Path(path)
    if not os.path.lexists(observation_path):
        raise QuillanObservationValidationError(
            f"Observation file is missing: {observation_path}"
        )
    if _path_is_link_like(observation_path) or not observation_path.is_file():
        raise QuillanObservationValidationError(
            f"Observation path must be an ordinary non-link file: {observation_path}"
        )
    try:
        data = observation_path.read_bytes()
    except OSError as error:
        raise QuillanObservationValidationError(
            f"Could not load observation {observation_path}: {error}"
        ) from error
    observation = _response_page_observation_from_json_bytes(
        data, source_description=str(observation_path)
    )
    if observation_path.name != f"{observation.observation_id}.json":
        raise QuillanObservationValidationError(
            "Observation filename does not match stored observation_id."
        )
    return observation


def load_contextual_response_page_observation(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    observation_id: str,
) -> QuillanResponsePageObservation:
    """Load one exact canonical observation after preflighting every ancestor."""
    if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
        raise QuillanObservationValidationError(
            "workspace_root must be an absolute Path."
        )
    root = Path(os.path.abspath(workspace_root))
    if (
        root != workspace_root
        or not os.path.lexists(root)
        or _path_is_link_like(root)
        or not root.is_dir()
    ):
        raise QuillanObservationValidationError(
            "workspace_root must be an existing canonical non-link directory."
        )
    validated_id = validate_observation_id(observation_id)
    expected = response_page_observation_path(root, work_ref, validated_id)
    try:
        checked = preflight_work_file_destination(
            root,
            work_ref,
            Path("scans") / "observations" / f"{validated_id}.json",
        )
    except QuillanWorkPathError as error:
        raise QuillanObservationValidationError(str(error)) from error
    if checked != expected:
        raise QuillanObservationValidationError(
            "Observation path is not the exact canonical work destination."
        )
    observation = load_response_page_observation(expected)
    if observation.observation_id != validated_id:
        raise QuillanObservationValidationError(
            "Loaded observation identity contradicts the requested observation_id."
        )
    return observation


def _response_page_observation_from_json_bytes(
    data: bytes,
    *,
    source_description: str,
) -> QuillanResponsePageObservation:
    if type(data) is not bytes:
        raise QuillanObservationValidationError("Observation JSON data must be bytes.")
    if type(source_description) is not str or not source_description:
        raise QuillanObservationValidationError(
            "Observation source description must be nonempty text."
        )
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QuillanObservationValidationError(
            f"Could not parse observation {source_description}: {error}"
        ) from error
    return response_page_observation_from_mapping(value)


load_quillan_response_page_observation = load_response_page_observation


@dataclass(frozen=True, slots=True)
class ObservationDiscoveryResult:
    """Strict deterministic observation discovery for one Quillan work item."""

    observations: tuple[QuillanResponsePageObservation, ...]
    observation_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if type(self.observations) is not tuple or type(self.observation_paths) is not tuple:
            raise QuillanObservationValidationError(
                "Observation discovery collections must be tuples."
            )
        if len(self.observations) != len(self.observation_paths):
            raise QuillanObservationValidationError(
                "Observation discovery collections must have equal lengths."
            )
        if any(type(item) is not QuillanResponsePageObservation for item in self.observations):
            raise QuillanObservationValidationError(
                "Observation discovery members have the wrong type."
            )
        if any(not isinstance(path, Path) for path in self.observation_paths):
            raise QuillanObservationValidationError(
                "Observation discovery paths have the wrong type."
            )
        for observation, path in zip(self.observations, self.observation_paths, strict=True):
            if not path.is_absolute() or Path(os.path.abspath(path)) != path:
                raise QuillanObservationValidationError(
                    "Observation discovery paths must be canonical and absolute."
                )
            if path.name != f"{observation.observation_id}.json":
                raise QuillanObservationValidationError(
                    "Observation discovery path contradicts observation_id."
                )
        ids = tuple(item.observation_id for item in self.observations)
        if len(set(ids)) != len(ids) or len(set(self.observation_paths)) != len(self.observation_paths):
            raise QuillanObservationValidationError(
                "Observation discovery members must be unique."
            )
        keys = tuple(_observation_discovery_sort_key(item) for item in self.observations)
        if keys != tuple(sorted(keys)):
            raise QuillanObservationValidationError(
                "Observation discovery members must be deterministically ordered."
            )


def discover_quillan_page_observations_status(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> ObservationDiscoveryResult:
    """Discover and verify only canonical observation JSON records."""
    if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
        raise QuillanObservationValidationError(
            "workspace_root must be an absolute Path."
        )
    root = Path(workspace_root)
    work_ref = quillan_work_ref(class_id, assignment_id)
    directory = response_page_observations_dir(root, work_ref)
    try:
        preflight_work_directory_destination(
            root, work_ref, Path("scans") / "observations"
        )
    except QuillanWorkPathError as error:
        raise QuillanObservationValidationError(str(error)) from error
    if not directory.exists():
        return ObservationDiscoveryResult((), ())
    if _path_is_link_like(directory) or not directory.is_dir():
        raise QuillanObservationValidationError(
            "Observation collection must be an ordinary non-link directory."
        )
    observations: list[QuillanResponsePageObservation] = []
    paths: list[Path] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if _path_is_link_like(path) or not path.is_file() or path.suffix != ".json":
            raise QuillanObservationValidationError(
                f"Unexpected child in observation collection: {path}"
            )
        observation_id = path.stem
        observation = load_contextual_response_page_observation(
            root, work_ref, observation_id
        )
        if (
            observation.class_id != class_id
            or observation.assignment_id != assignment_id
        ):
            raise QuillanObservationValidationError(
                "Observation identity does not match the selected work."
            )
        expected_path = response_page_observation_path(
            root, work_ref, observation.observation_id
        )
        if path != expected_path:
            raise QuillanObservationValidationError(
                "Observation is not stored at its canonical path."
            )
        extension = PurePosixPath(observation.routed_evidence_path).suffix
        expected_evidence = routed_evidence_path(
            root,
            work_ref,
            observation.issuance_id,
            observation.student_id,
            observation.logical_page,
            observation.observation_id,
            extension,
        )
        if root.joinpath(*PurePosixPath(observation.routed_evidence_path).parts) != expected_evidence:
            raise QuillanObservationValidationError(
                "Observation routed_evidence_path is not canonical."
            )
        verify_contextual_routed_page_evidence(
            root,
            work_ref,
            issuance_id=observation.issuance_id,
            student_id=observation.student_id,
            logical_page=observation.logical_page,
            observation_id=observation.observation_id,
            extension=extension,
            relative_path=observation.routed_evidence_path,
            expected_sha256=observation.routed_evidence_sha256,
            expected_size_bytes=observation.routed_evidence_size_bytes,
        )
        retained_path = root.joinpath(
            *PurePosixPath(observation.retained_source_path).parts
        )
        retained = RetainedSourceScan(
            source_scan_id=observation.source_scan_id,
            source_filename=observation.source_filename,
            source_sha256=observation.source_sha256,
            retained_source_path=retained_path,
            retained_source_relative_path=observation.retained_source_path,
            intake_timestamp=datetime.fromisoformat(observation.intake_timestamp),
            intake_date=date.fromisoformat(observation.intake_date),
        )
        try:
            validate_quillan_retained_source(
                retained,
                workspace_root=root,
                source_page_number=observation.source_page_number,
            )
        except ValueError as error:
            raise QuillanObservationValidationError(
                f"Observation retained source is invalid: {error}"
            ) from error
        observations.append(observation)
        paths.append(path)
    order = sorted(
        range(len(observations)),
        key=lambda index: (
            observations[index].issuance_id,
            observations[index].logical_page,
            observations[index].created_at,
            observations[index].source_scan_id,
            observations[index].source_page_number,
            observations[index].observation_id,
        ),
    )
    return ObservationDiscoveryResult(
        observations=tuple(observations[index] for index in order),
        observation_paths=tuple(paths[index] for index in order),
    )


def list_quillan_page_observations(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> tuple[QuillanResponsePageObservation, ...]:
    """Return all strictly verified observations in deterministic order."""
    try:
        return discover_quillan_page_observations_status(
            workspace_root, class_id, assignment_id
        ).observations
    except QuillanRoutedEvidenceMissingError as error:
        raise QuillanObservationDiscoveryError(
            "observation_missing_evidence",
            str(error),
            error,
        ) from error
    except QuillanRoutedEvidenceIntegrityError as error:
        raise QuillanObservationDiscoveryError(
            "observation_evidence_hash_mismatch",
            str(error),
            error,
        ) from error
    except QuillanRoutedEvidencePathError as error:
        raise QuillanObservationDiscoveryError(
            "observation_invalid",
            str(error),
            error,
        ) from error
    except (
        QuillanObservationValidationError,
        QuillanRetainedSourceError,
        QuillanWorkPathError,
        OSError,
        UnicodeError,
    ) as error:
        raise QuillanObservationDiscoveryError(
            "observation_invalid",
            str(error),
            error,
        ) from error


def group_response_page_observations_by_student(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> Mapping[str, tuple[QuillanResponsePageObservation, ...]]:
    """Group strictly verified observations by their persisted student identity."""
    grouped: dict[str, list[QuillanResponsePageObservation]] = {}
    for observation in list_quillan_page_observations(
        workspace_root, class_id, assignment_id
    ):
        grouped.setdefault(observation.student_id, []).append(observation)
    return MappingProxyType(
        {student_id: tuple(grouped[student_id]) for student_id in sorted(grouped)}
    )


def _path_is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


def _observation_discovery_sort_key(
    observation: QuillanResponsePageObservation,
) -> tuple[str, int, str, str, int, str]:
    return (
        observation.issuance_id,
        observation.logical_page,
        observation.created_at,
        observation.source_scan_id,
        observation.source_page_number,
        observation.observation_id,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QuillanObservationValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise QuillanObservationValidationError(f"Nonstandard JSON constant: {value}")


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise QuillanObservationValidationError(f"{field_name} must be a string.")
    try:
        return validate_identifier(value, field_name)
    except (IdentifierValidationError, TypeError) as error:
        raise QuillanObservationValidationError(str(error)) from error


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QuillanObservationValidationError(
            f"{field_name} must be a positive non-Boolean integer."
        )
    return value


def _timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise QuillanObservationValidationError(
            f"{field_name} must be a timezone-aware ISO timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise QuillanObservationValidationError(
            f"{field_name} must be a timezone-aware ISO timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise QuillanObservationValidationError(
            f"{field_name} must be a timezone-aware ISO timestamp."
        )
    return parsed


def _date(value: object, field_name: str) -> date:
    if not isinstance(value, str):
        raise QuillanObservationValidationError(f"{field_name} must be an ISO date.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuillanObservationValidationError(
            f"{field_name} must be an ISO date."
        ) from error


def _sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise QuillanObservationValidationError(
            f"{field_name} must be 64 lowercase hexadecimal characters."
        )
    return value


def _safe_filename(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise QuillanObservationValidationError(
            f"{field_name} must be a safe filename."
        )
    if (
        "/" in value
        or "\\" in value
        or any(
            unicodedata.category(character) in {"Cc", "Zl", "Zp"} for character in value
        )
    ):
        raise QuillanObservationValidationError(
            f"{field_name} must be a safe filename."
        )
    return value


def _relative_posix_path(value: object, field_name: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise QuillanObservationValidationError(
            f"{field_name} must be canonical workspace-relative POSIX text."
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(
        part in {"", ".", ".."}
        or any(
            unicodedata.category(character) in {"Cc", "Zl", "Zp"} for character in part
        )
        for part in path.parts
    ):
        raise QuillanObservationValidationError(
            f"{field_name} must be canonical workspace-relative POSIX text."
        )
    if path.as_posix() != value:
        raise QuillanObservationValidationError(
            f"{field_name} must be canonical workspace-relative POSIX text."
        )
    return path


def _freeze_json_mapping(
    value: object, field_name: str
) -> Mapping[str, FrozenJsonValue]:
    if not isinstance(value, Mapping):
        raise QuillanObservationValidationError(f"{field_name} must be an object.")
    result: dict[str, FrozenJsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise QuillanObservationValidationError(
                f"{field_name} keys must be strings."
            )
        result[key] = _freeze_json(item, f"{field_name}.{key}")
    return MappingProxyType(result)


def _freeze_json(value: object, field_name: str) -> FrozenJsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise QuillanObservationValidationError(f"{field_name} must be finite.")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, f"{field_name}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value, field_name)
    raise QuillanObservationValidationError(
        f"{field_name} must contain only JSON-native values."
    )


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


__all__ = [
    "OBSERVATION_ID_DOMAIN",
    "OBSERVATION_RECORD_TYPE",
    "OBSERVATION_SCHEMA_VERSION",
    "ObservationDiscoveryResult",
    "QuillanResponsePageObservation",
    "ROUTED_EVIDENCE_KINDS",
    "canonical_response_page_observation_json",
    "derive_observation_id",
    "discover_quillan_page_observations_status",
    "generate_observation_id",
    "group_response_page_observations_by_student",
    "load_quillan_response_page_observation",
    "load_contextual_response_page_observation",
    "load_response_page_observation",
    "list_quillan_page_observations",
    "response_page_observation_from_mapping",
    "response_page_observation_to_mapping",
    "validate_observation_id",
]

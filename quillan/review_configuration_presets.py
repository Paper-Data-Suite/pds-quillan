"""Reusable Quillan review-configuration preset records and persistence."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import (
    StandardsLibrary,
    load_workspace_standards_library,
)

from quillan._path_safety import is_link_like
from quillan.assignments import (
    AssignmentConfigError,
    validate_assignment_config,
    validate_assignment_standards_selection,
)
from quillan.assignment_workflows import build_assignment_config
from quillan.atomic_record_io import (
    AtomicRecordDurabilityError,
    create_exclusive_record,
)
from quillan.record_context import (
    canonical_workspace_root,
    load_quillan_assignment_context,
    mutable_json_copy,
)
from quillan.work_paths import quillan_work_ref

PRESET_SCHEMA_VERSION = "1"
PRESET_MODULE = "quillan"
PRESET_RECORD_TYPE = "review_configuration_preset"

PRESET_CONFIGURATION_FIELDS = (
    "writing_type",
    "standards_profile_id",
    "focus_standard_ids",
    "review_unit",
    "rating_scale",
    "basic_requirements",
    "minimum_requirement_policy",
)

_REQUIRED_PRESET_FIELDS = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "preset_id",
        "title",
        "description",
        *PRESET_CONFIGURATION_FIELDS,
        "created_at",
        "updated_at",
        "module_details",
    }
)


class ReviewConfigurationPresetError(ValueError):
    """A review-configuration preset is missing, invalid, stale, or unsafe."""


@dataclass(frozen=True, slots=True)
class ReviewConfigurationPresetInspection:
    """One discovered preset file with structural/current-standards status."""

    path: Path
    preset: dict[str, Any] | None
    structural_error: str | None
    standards_error: str | None

    @property
    def status(self) -> str:
        """Return ``valid``, ``invalid``, or ``stale``."""
        if self.structural_error is not None:
            return "invalid"
        if self.standards_error is not None:
            return "stale"
        return "valid"


@dataclass(frozen=True, slots=True)
class ReviewConfigurationPresetPlan:
    """A non-mutating, exact preset creation plan."""

    workspace_root: Path
    path: Path
    preset_json: str
    source_class_id: str | None = None
    source_assignment_id: str | None = None
    source_path: Path | None = None
    source_original_bytes: bytes | None = None

    @property
    def preset(self) -> dict[str, Any]:
        """Return a fresh mutable copy of the planned preset."""
        value = json.loads(self.preset_json)
        if not isinstance(value, dict):
            raise ReviewConfigurationPresetError(
                "Planned review-configuration preset is not an object."
            )
        return cast(dict[str, Any], value)


def build_review_configuration_preset(
    *,
    preset_id: str,
    title: str,
    description: str,
    writing_type: str,
    standards_profile_id: str,
    focus_standard_ids: list[str] | tuple[str, ...],
    review_unit: dict[str, Any],
    rating_scale: dict[str, Any],
    basic_requirements: dict[str, Any],
    minimum_requirement_policy: dict[str, Any],
    created_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build and structurally validate one schema-v1 preset."""
    timestamp = _normalize_timestamp(created_at)
    preset: dict[str, Any] = {
        "schema_version": PRESET_SCHEMA_VERSION,
        "module": PRESET_MODULE,
        "record_type": PRESET_RECORD_TYPE,
        "preset_id": preset_id,
        "title": title,
        "description": description,
        "writing_type": writing_type,
        "standards_profile_id": standards_profile_id,
        "focus_standard_ids": list(focus_standard_ids),
        "review_unit": copy.deepcopy(review_unit),
        "rating_scale": copy.deepcopy(rating_scale),
        "basic_requirements": copy.deepcopy(basic_requirements),
        "minimum_requirement_policy": copy.deepcopy(minimum_requirement_policy),
        "created_at": timestamp,
        "updated_at": timestamp,
        "module_details": {},
    }
    validate_review_configuration_preset(preset)
    return preset


def validate_review_configuration_preset(preset: dict[str, Any]) -> None:
    """Validate schema-v1 preset structure using assignment-v2 semantics."""
    if not isinstance(preset, dict):
        raise ReviewConfigurationPresetError(
            "Review-configuration preset must be an object."
        )
    actual_fields = frozenset(preset)
    missing = sorted(_REQUIRED_PRESET_FIELDS - actual_fields)
    unknown = sorted(actual_fields - _REQUIRED_PRESET_FIELDS)
    if missing:
        raise ReviewConfigurationPresetError(
            "Missing required review-configuration preset field(s): "
            + ", ".join(missing)
            + "."
        )
    if unknown:
        raise ReviewConfigurationPresetError(
            "Unknown review-configuration preset field(s): "
            + ", ".join(unknown)
            + "."
        )

    _require_fixed(preset["schema_version"], "schema_version", PRESET_SCHEMA_VERSION)
    _require_fixed(preset["module"], "module", PRESET_MODULE)
    _require_fixed(preset["record_type"], "record_type", PRESET_RECORD_TYPE)
    _require_identifier(preset["preset_id"], "preset_id")
    _require_non_empty_text(preset["title"], "title")
    _require_non_empty_text(preset["description"], "description")

    focus_standard_ids = preset["focus_standard_ids"]
    if not isinstance(focus_standard_ids, list):
        raise ReviewConfigurationPresetError(
            "Field 'focus_standard_ids' must be a list."
        )
    if len(set(_string_sequence(focus_standard_ids, "focus_standard_ids"))) != len(
        focus_standard_ids
    ):
        raise ReviewConfigurationPresetError(
            "Field 'focus_standard_ids' must not contain duplicate standard IDs."
        )

    try:
        assignment = _assignment_projection(preset)
        validate_assignment_config(assignment)
    except AssignmentConfigError as error:
        raise ReviewConfigurationPresetError(
            f"Invalid reusable review configuration: {error}"
        ) from error

    created_at = _parse_timestamp(preset["created_at"], "created_at")
    updated_at = _parse_timestamp(preset["updated_at"], "updated_at")
    if updated_at < created_at:
        raise ReviewConfigurationPresetError(
            "Field 'updated_at' must not precede field 'created_at'."
        )
    if not isinstance(preset["module_details"], dict):
        raise ReviewConfigurationPresetError("Field 'module_details' must be an object.")


def validate_review_configuration_preset_standards(
    preset: dict[str, Any],
    standards_library: StandardsLibrary,
) -> tuple[str, ...]:
    """Validate current Core profile/Focus Standard references for one preset."""
    validate_review_configuration_preset(preset)
    try:
        return validate_assignment_standards_selection(
            _assignment_projection(preset), standards_library
        )
    except AssignmentConfigError as error:
        raise ReviewConfigurationPresetError(
            f"Preset standards are not valid in the current workspace: {error}"
        ) from error


def review_configuration_preset_path(
    workspace_root: str | Path,
    preset_id: str,
) -> Path:
    """Return the canonical workspace-level path for one preset."""
    root = canonical_workspace_root(workspace_root)
    normalized_id = _require_identifier(preset_id, "preset_id")
    path = root / "shared" / "review_configuration_presets" / f"{normalized_id}.json"
    _preflight_preset_ancestors(root, path.parent)
    return path


def load_review_configuration_preset(path: str | Path) -> dict[str, Any]:
    """Load one strict UTF-8 JSON preset and validate filename identity."""
    preset_path = Path(path)
    if not os.path.lexists(preset_path):
        raise ReviewConfigurationPresetError(
            f"Review-configuration preset not found: {preset_path}"
        )
    if is_link_like(preset_path) or not preset_path.is_file():
        raise ReviewConfigurationPresetError(
            "Review-configuration preset must be an ordinary non-link file: "
            f"{preset_path}"
        )
    try:
        data = preset_path.read_bytes()
    except OSError as error:
        raise ReviewConfigurationPresetError(
            f"Could not read review-configuration preset {preset_path}: {error}"
        ) from error
    preset = _strict_json_object(data, preset_path)
    validate_review_configuration_preset(preset)
    if preset["preset_id"] != preset_path.stem:
        raise ReviewConfigurationPresetError(
            "Review-configuration preset preset_id does not match its filename: "
            f"{preset_path}"
        )
    return preset


def inspect_review_configuration_presets(
    workspace_root: str | Path,
) -> tuple[ReviewConfigurationPresetInspection, ...]:
    """Discover presets independently and classify structural/standards problems."""
    root = canonical_workspace_root(workspace_root)
    directory = root / "shared" / "review_configuration_presets"
    _preflight_preset_ancestors(root, directory)
    if not os.path.lexists(directory):
        return ()
    if is_link_like(directory) or not directory.is_dir():
        raise ReviewConfigurationPresetError(
            "Review-configuration preset directory must be an ordinary non-link "
            f"directory: {directory}"
        )

    try:
        standards_library = load_workspace_standards_library(root)
        standards_load_error: str | None = None
    except (OSError, ValueError) as error:
        standards_library = None
        standards_load_error = str(error)

    inspected: list[ReviewConfigurationPresetInspection] = []
    for path in directory.iterdir():
        if path.suffix.casefold() != ".json":
            continue
        preset: dict[str, Any] | None = None
        structural_error: str | None = None
        standards_error: str | None = None
        try:
            preset = load_review_configuration_preset(path)
        except (OSError, ValueError) as error:
            structural_error = str(error)
        if preset is not None:
            if standards_library is None:
                standards_error = (
                    "Could not load the current workspace standards library: "
                    f"{standards_load_error}"
                )
            else:
                try:
                    validate_review_configuration_preset_standards(
                        preset, standards_library
                    )
                except ReviewConfigurationPresetError as error:
                    standards_error = str(error)
        inspected.append(
            ReviewConfigurationPresetInspection(
                path=path,
                preset=preset,
                structural_error=structural_error,
                standards_error=standards_error,
            )
        )

    def sort_key(
        item: ReviewConfigurationPresetInspection,
    ) -> tuple[str, str]:
        if item.preset is None:
            return ("~", item.path.name.casefold())
        return (
            cast(str, item.preset["title"]).casefold(),
            cast(str, item.preset["preset_id"]),
        )

    return tuple(sorted(inspected, key=sort_key))




def load_current_review_configuration_preset(
    workspace_root: str | Path,
    preset_id: str,
) -> tuple[dict[str, Any], Path]:
    """Load one exact preset and revalidate its current Core standards."""
    root = canonical_workspace_root(workspace_root)
    path = review_configuration_preset_path(root, preset_id)
    preset = load_review_configuration_preset(path)
    _validate_current_standards(root, preset)
    return preset, path




def require_current_review_configuration_preset_matches(
    workspace_root: str | Path,
    reviewed_preset: dict[str, Any],
) -> None:
    """Fail if the exact reviewed preset model is no longer current and valid."""
    validate_review_configuration_preset(reviewed_preset)
    preset_id = reviewed_preset["preset_id"]
    if not isinstance(preset_id, str):
        raise ReviewConfigurationPresetError(
            "Reviewed preset_id must be an identifier string."
        )
    current, _path = load_current_review_configuration_preset(
        workspace_root, preset_id
    )
    if current != reviewed_preset:
        raise ReviewConfigurationPresetError(
            "Review-configuration preset changed after review; select and "
            "review the preset again before saving the assignment."
        )


def plan_review_configuration_preset_creation(
    workspace_root: str | Path,
    *,
    preset_id: str,
    title: str,
    description: str,
    writing_type: str,
    standards_profile_id: str,
    focus_standard_ids: list[str] | tuple[str, ...],
    review_unit: dict[str, Any],
    rating_scale: dict[str, Any],
    basic_requirements: dict[str, Any],
    minimum_requirement_policy: dict[str, Any],
    created_at: datetime | str | None = None,
) -> ReviewConfigurationPresetPlan:
    """Plan direct preset creation without creating directories or files."""
    root = canonical_workspace_root(workspace_root)
    preset = build_review_configuration_preset(
        preset_id=preset_id,
        title=title,
        description=description,
        writing_type=writing_type,
        standards_profile_id=standards_profile_id,
        focus_standard_ids=focus_standard_ids,
        review_unit=review_unit,
        rating_scale=rating_scale,
        basic_requirements=basic_requirements,
        minimum_requirement_policy=minimum_requirement_policy,
        created_at=created_at,
    )
    _validate_current_standards(root, preset)
    path = review_configuration_preset_path(root, preset_id)
    _require_create_only_destination(root, path)
    return _build_plan(root=root, path=path, preset=preset)


def plan_review_configuration_preset_from_assignment(
    workspace_root: str | Path,
    *,
    source_class_id: str,
    source_assignment_id: str,
    preset_id: str,
    title: str,
    description: str,
    created_at: datetime | str | None = None,
) -> ReviewConfigurationPresetPlan:
    """Plan a preset from one exact canonical assignment and its safe allowlist."""
    root = canonical_workspace_root(workspace_root)
    try:
        _require_identifier(source_class_id, "source_class_id")
        _require_identifier(source_assignment_id, "source_assignment_id")
        source_context = load_quillan_assignment_context(
            root, quillan_work_ref(source_class_id, source_assignment_id)
        )
    except (OSError, ValueError) as error:
        raise ReviewConfigurationPresetError(
            f"Could not load source assignment: {error}"
        ) from error

    source = mutable_json_copy(source_context.assignment)
    try:
        standards_library = load_workspace_standards_library(root)
        validate_assignment_standards_selection(source, standards_library)
    except (OSError, ValueError) as error:
        raise ReviewConfigurationPresetError(
            "Source assignment standards are not valid in the current workspace: "
            f"{error}"
        ) from error

    preset = build_review_configuration_preset(
        preset_id=preset_id,
        title=title,
        description=description,
        writing_type=cast(str, source["writing_type"]),
        standards_profile_id=cast(str, source["standards_profile_id"]),
        focus_standard_ids=cast(list[str], source["focus_standard_ids"]),
        review_unit=cast(dict[str, Any], source["review_unit"]),
        rating_scale=cast(dict[str, Any], source["rating_scale"]),
        basic_requirements=cast(dict[str, Any], source["basic_requirements"]),
        minimum_requirement_policy=cast(
            dict[str, Any], source["minimum_requirement_policy"]
        ),
        created_at=created_at,
    )
    validate_review_configuration_preset_standards(preset, standards_library)
    path = review_configuration_preset_path(root, preset_id)
    _require_create_only_destination(root, path)
    plan = _build_plan(root=root, path=path, preset=preset)
    return ReviewConfigurationPresetPlan(
        workspace_root=plan.workspace_root,
        path=plan.path,
        preset_json=plan.preset_json,
        source_class_id=source_class_id,
        source_assignment_id=source_assignment_id,
        source_path=source_context.paths.assignment_path,
        source_original_bytes=source_context.assignment_record.original_bytes,
    )


def commit_review_configuration_preset(
    plan: ReviewConfigurationPresetPlan,
) -> Path:
    """Commit a reviewed preset plan using create-only guarded persistence."""
    if type(plan) is not ReviewConfigurationPresetPlan:
        raise ReviewConfigurationPresetError(
            "plan must be a ReviewConfigurationPresetPlan."
        )
    preset = plan.preset
    validate_review_configuration_preset(preset)

    if plan.source_path is not None:
        if (
            plan.source_class_id is None
            or plan.source_assignment_id is None
            or plan.source_original_bytes is None
        ):
            raise ReviewConfigurationPresetError(
                "Source-backed preset plan is internally incomplete."
            )
        try:
            source_context = load_quillan_assignment_context(
                plan.workspace_root,
                quillan_work_ref(
                    plan.source_class_id,
                    plan.source_assignment_id,
                ),
            )
        except (OSError, ValueError) as error:
            raise ReviewConfigurationPresetError(
                "Source assignment changed or became unavailable after planning: "
                f"{error}"
            ) from error
        if (
            source_context.paths.assignment_path != plan.source_path
            or source_context.assignment_record.original_bytes
            != plan.source_original_bytes
        ):
            raise ReviewConfigurationPresetError(
                "Source assignment changed after preview; plan the preset again "
                "before saving."
            )

    _validate_current_standards(plan.workspace_root, preset)
    _require_create_only_destination(plan.workspace_root, plan.path)

    data = _serialize_preset(preset)
    created_directories: list[Path] = []
    try:
        created_directories = _ensure_preset_parent(plan.workspace_root, plan.path)

        def preflight() -> None:
            _preflight_preset_file_path(plan.workspace_root, plan.path)

        def verify_bytes(actual: bytes) -> None:
            loaded = _strict_json_object(actual, plan.path)
            validate_review_configuration_preset(loaded)
            if loaded != preset:
                raise ReviewConfigurationPresetError(
                    "Persisted review-configuration preset does not match the "
                    "reviewed plan."
                )

        create_exclusive_record(
            plan.path,
            data,
            preflight=preflight,
            verify_bytes=verify_bytes,
        )
    except AtomicRecordDurabilityError:
        raise
    except (OSError, ValueError) as error:
        _cleanup_empty_created_directories(created_directories)
        raise ReviewConfigurationPresetError(
            f"Review-configuration preset was not committed: {error}"
        ) from error
    return plan.path


def _build_plan(
    *,
    root: Path,
    path: Path,
    preset: dict[str, Any],
) -> ReviewConfigurationPresetPlan:
    return ReviewConfigurationPresetPlan(
        workspace_root=root,
        path=path,
        preset_json=json.dumps(
            preset, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ),
    )


def _assignment_projection(preset: dict[str, Any]) -> dict[str, Any]:
    """Project reusable fields through the authoritative assignment-v2 validator."""
    return build_assignment_config(
        assignment_id="preset_validation",
        title="Review configuration preset validation",
        class_ids=["preset_validation"],
        writing_type=cast(str, preset["writing_type"]),
        student_prompt="Review configuration preset validation.",
        standards_profile_id=cast(str, preset["standards_profile_id"]),
        focus_standard_ids=cast(list[str], preset["focus_standard_ids"]),
        review_unit=cast(dict[str, Any], preset["review_unit"]),
        rating_scale=cast(dict[str, Any], preset["rating_scale"]),
        basic_requirements=cast(dict[str, Any], preset["basic_requirements"]),
        minimum_requirement_policy=cast(
            dict[str, Any], preset["minimum_requirement_policy"]
        ),
        created_at=cast(str, preset["created_at"]),
    )


def _validate_current_standards(root: Path, preset: dict[str, Any]) -> None:
    try:
        library = load_workspace_standards_library(root)
        validate_review_configuration_preset_standards(preset, library)
    except (OSError, ValueError) as error:
        raise ReviewConfigurationPresetError(
            f"Preset standards are not valid in the current workspace: {error}"
        ) from error


def _require_create_only_destination(root: Path, path: Path) -> None:
    _preflight_preset_file_path(root, path)
    if os.path.lexists(path):
        raise ReviewConfigurationPresetError(
            f"Review-configuration preset already exists: {path}"
        )


def _preflight_preset_file_path(root: Path, path: Path) -> None:
    _preflight_preset_ancestors(root, path.parent)
    expected_parent = root / "shared" / "review_configuration_presets"
    if path.parent != expected_parent:
        raise ReviewConfigurationPresetError(
            "Review-configuration preset path is not canonical."
        )
    if os.path.lexists(path) and (is_link_like(path) or not path.is_file()):
        raise ReviewConfigurationPresetError(
            "Review-configuration preset target is not an ordinary non-link file: "
            f"{path}"
        )


def _preflight_preset_ancestors(root: Path, directory: Path) -> None:
    expected = root / "shared" / "review_configuration_presets"
    if directory != expected:
        raise ReviewConfigurationPresetError(
            "Review-configuration preset directory is not canonical."
        )
    for path in (root / "shared", expected):
        if not os.path.lexists(path):
            continue
        if is_link_like(path) or not path.is_dir():
            raise ReviewConfigurationPresetError(
                "Review-configuration preset path contains a symlink, junction, "
                f"reparse point, or non-directory: {path}"
            )


def _ensure_preset_parent(root: Path, path: Path) -> list[Path]:
    _preflight_preset_ancestors(root, path.parent)
    created: list[Path] = []
    for directory in (root / "shared", path.parent):
        existed = os.path.lexists(directory)
        try:
            directory.mkdir(exist_ok=True)
        except OSError as error:
            _cleanup_empty_created_directories(created)
            raise ReviewConfigurationPresetError(
                f"Could not create review-configuration preset directory "
                f"{directory}: {error}"
            ) from error
        if not existed:
            created.append(directory)
        _preflight_preset_ancestors(root, path.parent)
    return created


def _cleanup_empty_created_directories(directories: list[Path]) -> None:
    for directory in reversed(directories):
        try:
            directory.rmdir()
        except OSError:
            pass


def _serialize_preset(preset: dict[str, Any]) -> bytes:
    return (
        json.dumps(preset, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


def _strict_json_object(data: bytes, path: Path) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReviewConfigurationPresetError(
                    f"Duplicate JSON object key {key!r}: {path}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ReviewConfigurationPresetError(
            f"Invalid JSON constant {value!r}: {path}"
        )

    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewConfigurationPresetError(
            f"Review-configuration preset is not valid strict UTF-8 JSON: "
            f"{path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ReviewConfigurationPresetError(
            f"Review-configuration preset must be a JSON object: {path}"
        )
    return cast(dict[str, Any], value)


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        timestamp = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        _parse_timestamp(value, "created_at")
        return value
    else:
        raise ReviewConfigurationPresetError(
            "created_at must be a datetime, timezone-aware ISO 8601 string, or None."
        )
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReviewConfigurationPresetError(
            "created_at must include timezone information."
        )
    return timestamp.isoformat()


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return timestamp


def _string_sequence(values: list[Any], field: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ReviewConfigurationPresetError(
                f"Each value in '{field}' must be a non-empty string."
            )
        normalized.append(value)
    if not normalized:
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must not be empty."
        )
    return tuple(normalized)


def _require_fixed(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be {expected!r}; got {value!r}."
        )


def _require_identifier(value: Any, field: str) -> str:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise ReviewConfigurationPresetError(str(error)) from error
    if not isinstance(value, str):
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be a valid identifier string."
        )
    return value


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewConfigurationPresetError(
            f"Field '{field}' must be a non-empty string."
        )
    return value

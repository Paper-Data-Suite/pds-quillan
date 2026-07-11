"""Conservative retained-source and routed-evidence filing."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.scan_retention import (
    RetainedSourceScan as RetainedSourceScan,
    SourceRetentionError,
    retain_source_scan,
)

from quillan.route_planning import RoutePlan
from quillan.storage import assignment_scans_dir

_COPY_BUFFER_SIZE: Final[int] = 1024 * 1024
_MAX_DUPLICATE_ATTEMPTS: Final[int] = 10_000
_SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff"}
)


class EvidenceFilingError(RuntimeError):
    """Raised when retained source or routed evidence cannot be filed safely."""


@dataclass(frozen=True, slots=True)
class RoutedEvidenceFile:
    """Provenance for one successfully filed Quillan response page."""

    class_id: str
    assignment_id: str
    student_id: str
    page_number: int
    retained_source: RetainedSourceScan
    routed_evidence_path: Path
    routed_evidence_relative_path: str
    duplicate_number: int | None


def file_routed_response_evidence(
    workspace_root: str | Path,
    *,
    route_plan: RoutePlan,
    source_file_path: str | Path,
    intake_timestamp: datetime,
    intake_date: date | str | None = None,
    routed_source_file_path: str | Path | None = None,
    routed_extension: str | None = None,
) -> RoutedEvidenceFile:
    """Retain a selected source and file one routed response-page artifact.

    ``routed_source_file_path`` may identify an already-extracted page artifact.
    When omitted, the newly retained source itself is copied as routed evidence.
    """
    root = _resolved_workspace_root(workspace_root)
    routed_dir, page_number = _validated_route_plan(root, route_plan)
    routed_input = (
        _readable_regular_file(
            routed_source_file_path,
            "routed_source_file_path",
        )
        if routed_source_file_path is not None
        else None
    )
    if routed_extension is not None:
        extension = _normalized_extension(routed_extension)
    elif routed_input is not None:
        extension = _normalized_extension(routed_input.suffix)
    else:
        extension = None

    try:
        retained_source = retain_source_scan(
            root,
            source_file_path,
            intake_timestamp=intake_timestamp,
            intake_date=intake_date,
        )
    except SourceRetentionError as error:
        raise EvidenceFilingError(f"Could not retain source scan: {error}") from error

    if extension is None:
        extension = _normalized_extension(retained_source.retained_source_path.suffix)

    routed_input = (
        retained_source.retained_source_path if routed_input is None else routed_input
    )
    _create_directory(routed_dir, root, "routed evidence directory")
    routed_path, duplicate_number = _copy_routed_evidence(
        routed_input,
        routed_dir,
        route_plan.student_id,
        page_number,
        extension,
    )

    return RoutedEvidenceFile(
        class_id=route_plan.class_id,
        assignment_id=route_plan.assignment_id,
        student_id=route_plan.student_id,
        page_number=page_number,
        retained_source=retained_source,
        routed_evidence_path=routed_path,
        routed_evidence_relative_path=_workspace_relative(routed_path, root),
        duplicate_number=duplicate_number,
    )


def _resolved_workspace_root(workspace_root: str | Path) -> Path:
    try:
        root = Path(workspace_root).resolve(strict=False)
        if not root.is_dir():
            raise EvidenceFilingError(
                f"Workspace root is not an existing directory: {root}"
            )
        return root
    except (OSError, TypeError, ValueError) as error:
        raise EvidenceFilingError(f"Invalid workspace root: {error}") from error


def _validated_route_plan(root: Path, route_plan: RoutePlan) -> tuple[Path, int]:
    if not isinstance(route_plan, RoutePlan):
        raise EvidenceFilingError("route_plan must be a successful RoutePlan.")
    try:
        validate_identifier(route_plan.class_id, "class_id")
        validate_identifier(route_plan.assignment_id, "assignment_id")
        validate_identifier(route_plan.student_id, "student_id")
    except IdentifierValidationError as error:
        raise EvidenceFilingError(f"Unsafe route identity: {error}") from error

    page_number = route_plan.page_number
    if (
        page_number is None
        or isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
    ):
        raise EvidenceFilingError(
            "RoutePlan.page_number must be a positive integer for evidence filing."
        )

    try:
        routed_dir = route_plan.routed_evidence_dir.resolve(strict=False)
    except (OSError, TypeError, ValueError) as error:
        raise EvidenceFilingError(
            f"Invalid routed evidence directory: {error}"
        ) from error
    _require_contained(routed_dir, root, "routed evidence directory")
    expected_routed_dir = assignment_scans_dir(
        root,
        route_plan.class_id,
        route_plan.assignment_id,
    ).resolve(strict=False)
    if routed_dir != expected_routed_dir:
        raise EvidenceFilingError(
            "RoutePlan.routed_evidence_dir does not match its class_id and "
            "assignment_id."
        )
    return routed_dir, page_number


def _readable_regular_file(value: str | Path, field_name: str) -> Path:
    try:
        path = Path(value)
        if not path.is_file():
            raise EvidenceFilingError(
                f"{field_name} must identify an existing regular file: {path}"
            )
        with path.open("rb"):
            pass
        return path
    except EvidenceFilingError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise EvidenceFilingError(f"Could not read {field_name}: {error}") from error


def _copy_exclusive(source: Path, destination: Path) -> None:
    destination_created = False
    try:
        with source.open("rb") as source_file:
            with destination.open("xb") as destination_file:
                destination_created = True
                shutil.copyfileobj(
                    source_file,
                    destination_file,
                    length=_COPY_BUFFER_SIZE,
                )
    except FileExistsError:
        raise
    except OSError:
        if destination_created:
            _remove_incomplete_copy(destination)
        raise


def _copy_routed_evidence(
    source: Path,
    routed_dir: Path,
    student_id: str,
    page_number: int,
    extension: str,
) -> tuple[Path, int | None]:
    base_name = f"response_{student_id}_pg_{page_number:03d}"
    for duplicate_number in range(_MAX_DUPLICATE_ATTEMPTS):
        duplicate_suffix = (
            "" if duplicate_number == 0 else f"__dup_{duplicate_number:03d}"
        )
        candidate = (routed_dir / f"{base_name}{duplicate_suffix}{extension}").resolve(
            strict=False
        )
        _require_contained(candidate, routed_dir, "routed evidence path")
        try:
            _copy_exclusive(source, candidate)
        except FileExistsError:
            continue
        except OSError as error:
            raise EvidenceFilingError(
                f"Could not copy routed evidence to {candidate}: {error}"
            ) from error
        return candidate, duplicate_number or None

    raise EvidenceFilingError(
        "Could not choose an available routed evidence filename after "
        f"{_MAX_DUPLICATE_ATTEMPTS} attempts."
    )


def _normalized_extension(extension: str) -> str:
    if not isinstance(extension, str):
        raise EvidenceFilingError("routed_extension must be a string.")
    normalized = extension.lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in _SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise EvidenceFilingError(
            f"Unsupported routed evidence extension; expected one of: {allowed}."
        )
    return normalized


def _create_directory(path: Path, root: Path, description: str) -> None:
    _require_contained(path, root, description)
    try:
        path.mkdir(parents=True, exist_ok=True)
        resolved_path = path.resolve(strict=True)
    except OSError as error:
        raise EvidenceFilingError(f"Could not create {description}: {error}") from error
    _require_contained(resolved_path, root, description)
    if not resolved_path.is_dir():
        raise EvidenceFilingError(f"{description.capitalize()} is not a directory.")


def _require_contained(path: Path, parent: Path, description: str) -> None:
    if path == parent or path.is_relative_to(parent):
        return
    raise EvidenceFilingError(f"{description.capitalize()} escapes its allowed root.")


def _workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise EvidenceFilingError("Filed path is outside the workspace root.") from error


def _remove_incomplete_copy(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

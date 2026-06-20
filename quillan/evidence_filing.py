"""Conservative retained-source and routed-evidence filing."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.scan_routes import (
    ScanRouteError,
    build_retained_source_filename,
    retained_source_scan_path,
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
class RetainedSourceScan:
    """Provenance for one canonical retained source intake event."""

    source_scan_id: str
    source_filename: str
    source_sha256: str
    retained_source_path: Path
    retained_source_relative_path: str


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
    source_path = _readable_regular_file(source_file_path, "source_file_path")
    routed_input = (
        _readable_regular_file(
            routed_source_file_path,
            "routed_source_file_path",
        )
        if routed_source_file_path is not None
        else None
    )

    source_sha256 = _sha256_file(source_path, "source_file_path")
    try:
        retained_filename = build_retained_source_filename(
            intake_timestamp=intake_timestamp,
            original_filename=source_path.name,
            sha256_hex=source_sha256,
        )
        source_date = (
            intake_timestamp.astimezone(timezone.utc).date()
            if intake_date is None
            else intake_date
        )
        retained_path = retained_source_scan_path(
            root,
            intake_date=source_date,
            retained_filename=retained_filename,
        ).resolve(strict=False)
    except (ScanRouteError, OSError, ValueError) as error:
        raise EvidenceFilingError(f"Invalid retained source route: {error}") from error

    routed_input_for_extension = (
        source_path if routed_input is None else routed_input
    )
    extension = _normalized_extension(
        routed_extension
        if routed_extension is not None
        else routed_input_for_extension.suffix
    )

    retained_dir = retained_path.parent
    _require_contained(retained_path, retained_dir, "retained source path")
    _require_contained(retained_dir, root, "retained source directory")
    _create_directory(retained_dir, root, "retained source directory")

    try:
        copied_sha256 = _copy_exclusive_with_sha256(source_path, retained_path)
    except FileExistsError as error:
        raise EvidenceFilingError(
            f"Retained source destination already exists: {retained_path}"
        ) from error
    except OSError as error:
        raise EvidenceFilingError(
            f"Could not copy retained source to {retained_path}: {error}"
        ) from error
    if copied_sha256 != source_sha256:
        _remove_incomplete_copy(retained_path)
        raise EvidenceFilingError(
            "Source file changed while it was being retained; no retained copy "
            "was kept."
        )

    retained_source = RetainedSourceScan(
        source_scan_id=f"scan_{retained_path.stem}",
        source_filename=source_path.name,
        source_sha256=source_sha256,
        retained_source_path=retained_path,
        retained_source_relative_path=_workspace_relative(retained_path, root),
    )

    routed_input = retained_path if routed_input is None else routed_input
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


def _sha256_file(path: Path, field_name: str) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(_COPY_BUFFER_SIZE):
                digest.update(chunk)
    except OSError as error:
        raise EvidenceFilingError(f"Could not read {field_name}: {error}") from error
    return digest.hexdigest()


def _copy_exclusive_with_sha256(source: Path, destination: Path) -> str:
    digest = hashlib.sha256()
    destination_created = False
    try:
        with source.open("rb") as source_file:
            with destination.open("xb") as destination_file:
                destination_created = True
                while chunk := source_file.read(_COPY_BUFFER_SIZE):
                    destination_file.write(chunk)
                    digest.update(chunk)
    except FileExistsError:
        raise
    except OSError:
        if destination_created:
            _remove_incomplete_copy(destination)
        raise
    return digest.hexdigest()


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

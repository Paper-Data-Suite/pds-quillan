"""Assembly of routed Quillan evidence into new submission manifests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Sequence

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.submission_manifest import (
    ALLOWED_EVIDENCE_STATES,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

_RETAINED_SOURCE_FIELDS: Final[tuple[str, ...]] = (
    "source_scan_id",
    "source_filename",
    "source_sha256",
    "retained_source_path",
)
_ALLOWED_CALLER_EVIDENCE_ROLES: Final[frozenset[str]] = frozenset(
    {"candidate", "replacement", "excluded"}
)
_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Fa-f]{64}$")


class SubmissionAssemblyError(ValueError):
    """Raised when routed evidence cannot be assembled into a manifest."""


@dataclass(frozen=True, slots=True)
class RoutedSubmissionEvidence:
    """Caller-provided metadata for one routed response-page artifact."""

    page_number: int
    routed_evidence_path: str | Path
    retained_source_path: str | Path | None = None
    source_scan_id: str | None = None
    source_filename: str | None = None
    source_sha256: str | None = None
    source_page_number: int | None = None
    duplicate_number: int | None = None
    created_at: datetime | str | None = None
    evidence_state: str = "active"
    module_details: dict[str, Any] | None = None
    evidence_role: str | None = None


@dataclass(frozen=True, slots=True)
class _NormalizedEvidence:
    page_number: int
    routed_evidence_path: str
    retained_source: dict[str, Any] | None
    duplicate_number: int | None
    created_at: str
    evidence_state: str
    evidence_role: str | None
    module_details: dict[str, Any]


def build_submission_manifest(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    evidence_items: Sequence[RoutedSubmissionEvidence],
    *,
    expected_pages: int | None = None,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build a v0.6 submission manifest from routed evidence without writing."""
    root = _resolved_workspace_root(workspace_root)
    _validate_identifiers(class_id, assignment_id, student_id)
    _validate_optional_positive_integer(expected_pages, "expected_pages")

    now = datetime.now(timezone.utc).isoformat()
    manifest_created_at = _normalize_timestamp(
        created_at, "created_at", default=now
    )
    manifest_updated_at = _normalize_timestamp(
        updated_at, "updated_at", default=now
    )

    normalized = [
        _normalize_evidence(item, root, manifest_created_at)
        for item in evidence_items
    ]
    normalized.sort(key=_evidence_sort_key)

    evidence_by_page: dict[int, list[tuple[str, _NormalizedEvidence]]] = {}
    for index, item in enumerate(normalized, start=1):
        evidence_id = f"evidence_{index:03d}"
        evidence_by_page.setdefault(item.page_number, []).append(
            (evidence_id, item)
        )

    page_numbers = set(evidence_by_page)
    if expected_pages is not None:
        page_numbers.update(range(1, expected_pages + 1))

    pages = [
        _build_page(page_number, evidence_by_page.get(page_number, []))
        for page_number in sorted(page_numbers)
    ]
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "expected_pages": expected_pages,
        "submission_state": "unreviewed",
        "pages": pages,
        "created_at": manifest_created_at,
        "updated_at": manifest_updated_at,
        "module_details": {},
    }
    validate_submission_manifest(manifest)
    return manifest


def assemble_submission_manifest(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    evidence_items: Sequence[RoutedSubmissionEvidence],
    *,
    expected_pages: int | None = None,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
) -> Path:
    """Assemble and write a v0.6 submission manifest from routed evidence."""
    manifest = build_submission_manifest(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        evidence_items,
        expected_pages=expected_pages,
        created_at=created_at,
        updated_at=updated_at,
    )
    path = submission_manifest_path(
        workspace_root, class_id, assignment_id, student_id
    )
    return write_submission_manifest(path, manifest, overwrite=overwrite)


def _normalize_evidence(
    item: RoutedSubmissionEvidence,
    root: Path,
    manifest_created_at: str,
) -> _NormalizedEvidence:
    if not isinstance(item, RoutedSubmissionEvidence):
        raise SubmissionAssemblyError(
            "Each evidence item must be a RoutedSubmissionEvidence instance."
        )
    page_number = _validate_positive_integer(item.page_number, "page_number")
    duplicate_number = _validate_optional_positive_integer(
        item.duplicate_number, "duplicate_number"
    )
    if (
        not isinstance(item.evidence_state, str)
        or item.evidence_state not in ALLOWED_EVIDENCE_STATES
    ):
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_STATES))
        raise SubmissionAssemblyError(
            f"Invalid evidence_state {item.evidence_state!r}. "
            f"Allowed values: {allowed}."
        )
    if (
        item.evidence_role is not None
        and (
            not isinstance(item.evidence_role, str)
            or item.evidence_role not in _ALLOWED_CALLER_EVIDENCE_ROLES
        )
    ):
        allowed = ", ".join(sorted(_ALLOWED_CALLER_EVIDENCE_ROLES))
        raise SubmissionAssemblyError(
            f"Invalid evidence_role {item.evidence_role!r}. "
            f"Allowed caller-provided values: {allowed}."
        )

    module_details = {} if item.module_details is None else item.module_details
    _validate_json_object(module_details, "module_details")

    return _NormalizedEvidence(
        page_number=page_number,
        routed_evidence_path=_workspace_relative_path(
            item.routed_evidence_path, root, "routed_evidence_path"
        ),
        retained_source=_normalize_retained_source(item, root),
        duplicate_number=duplicate_number,
        created_at=_normalize_timestamp(
            item.created_at,
            "evidence created_at",
            default=manifest_created_at,
        ),
        evidence_state=item.evidence_state,
        evidence_role=item.evidence_role,
        module_details=module_details.copy(),
    )


def _normalize_retained_source(
    item: RoutedSubmissionEvidence, root: Path
) -> dict[str, Any] | None:
    values = {
        "source_scan_id": item.source_scan_id,
        "source_filename": item.source_filename,
        "source_sha256": item.source_sha256,
        "retained_source_path": item.retained_source_path,
    }
    supplied = [field for field, value in values.items() if value is not None]
    if not supplied:
        if item.source_page_number is not None:
            raise SubmissionAssemblyError(
                "Retained-source provenance is partial; source_page_number "
                "requires all retained-source fields."
            )
        return None
    if len(supplied) != len(_RETAINED_SOURCE_FIELDS):
        missing = ", ".join(
            field for field in _RETAINED_SOURCE_FIELDS if values[field] is None
        )
        raise SubmissionAssemblyError(
            f"Retained-source provenance is partial; missing: {missing}."
        )

    source_page_number = _validate_optional_positive_integer(
        item.source_page_number, "source_page_number"
    )
    _validate_non_empty_string(item.source_scan_id, "source_scan_id")
    source_filename = _validate_non_empty_string(
        item.source_filename, "source_filename"
    )
    if (
        "/" in source_filename
        or "\\" in source_filename
        or "\0" in source_filename
        or source_filename in {".", ".."}
    ):
        raise SubmissionAssemblyError(
            "source_filename must be a filename only."
        )
    if (
        not isinstance(item.source_sha256, str)
        or not _SHA256_PATTERN.fullmatch(item.source_sha256)
    ):
        raise SubmissionAssemblyError(
            "source_sha256 must be a 64-character hexadecimal SHA-256 digest."
        )
    retained_path = item.retained_source_path
    assert retained_path is not None
    return {
        "source_scan_id": item.source_scan_id,
        "source_filename": item.source_filename,
        "source_sha256": item.source_sha256,
        "retained_source_path": _workspace_relative_path(
            retained_path, root, "retained_source_path"
        ),
        "source_page_number": source_page_number,
    }


def _build_page(
    page_number: int,
    items: list[tuple[str, _NormalizedEvidence]],
) -> dict[str, Any]:
    if not items:
        return {
            "page_number": page_number,
            "page_state": "missing",
            "selected_evidence_id": None,
            "evidence": [],
        }

    auto_selected = len(items) == 1 and _can_auto_select(items[0][1])
    evidence = [
        {
            "evidence_id": evidence_id,
            "routed_evidence_path": item.routed_evidence_path,
            "evidence_role": (
                "selected" if auto_selected else _manifest_evidence_role(item)
            ),
            "evidence_state": item.evidence_state,
            "duplicate_number": item.duplicate_number,
            "created_at": item.created_at,
            "retained_source": item.retained_source,
            "module_details": item.module_details,
        }
        for evidence_id, item in items
    ]
    if all(_is_excluded(item) for _, item in items):
        page_state = "excluded"
    elif len(items) > 1:
        page_state = "duplicate"
    elif _requires_rescan(items[0][1]):
        page_state = "needs_rescan"
    else:
        page_state = "present"

    return {
        "page_number": page_number,
        "page_state": page_state,
        "selected_evidence_id": items[0][0] if auto_selected else None,
        "evidence": evidence,
    }


def _can_auto_select(item: _NormalizedEvidence) -> bool:
    return item.evidence_role is None and item.evidence_state == "active"


def _manifest_evidence_role(item: _NormalizedEvidence) -> str:
    if item.evidence_role is not None:
        return item.evidence_role
    if item.evidence_state == "excluded":
        return "excluded"
    return "candidate"


def _is_excluded(item: _NormalizedEvidence) -> bool:
    return (
        item.evidence_role == "excluded" or item.evidence_state == "excluded"
    )


def _requires_rescan(item: _NormalizedEvidence) -> bool:
    return (
        item.evidence_role == "replacement"
        or item.evidence_state in {"damaged", "needs_rescan"}
    )


def _evidence_sort_key(item: _NormalizedEvidence) -> tuple[Any, ...]:
    retained = item.retained_source or {}
    return (
        item.page_number,
        item.duplicate_number is not None,
        item.duplicate_number or 0,
        item.routed_evidence_path,
        item.created_at,
        item.evidence_state,
        item.evidence_role or "",
        retained.get("retained_source_path", ""),
        retained.get("source_scan_id", ""),
        retained.get("source_filename", ""),
        retained.get("source_sha256", ""),
        retained.get("source_page_number") or 0,
        json.dumps(item.module_details, sort_keys=True, ensure_ascii=False),
    )


def _resolved_workspace_root(workspace_root: str | Path) -> Path:
    try:
        return Path(workspace_root).resolve(strict=False)
    except (OSError, TypeError, ValueError) as error:
        raise SubmissionAssemblyError(f"Invalid workspace_root: {error}") from error


def _workspace_relative_path(
    value: str | Path, root: Path, field: str
) -> str:
    if not isinstance(value, (str, Path)):
        raise SubmissionAssemblyError(f"{field} must be a string or Path.")
    try:
        raw = str(value)
    except (TypeError, ValueError) as error:
        raise SubmissionAssemblyError(f"Invalid {field}: {error}") from error
    if not raw:
        raise SubmissionAssemblyError(f"{field} must be a non-empty path.")
    if "\0" in raw:
        raise SubmissionAssemblyError(f"{field} must not contain null bytes.")

    variants = (PurePosixPath(raw), PureWindowsPath(raw))
    is_absolute = any(path.anchor or path.drive for path in variants)
    if not is_absolute:
        components = re.split(r"[\\/]", raw)
        if "." in components or ".." in components:
            raise SubmissionAssemblyError(
                f"{field} must not contain '.' or '..' path components."
            )
        return raw

    try:
        absolute = Path(value).resolve(strict=False)
        relative = absolute.relative_to(root)
    except (OSError, TypeError, ValueError) as error:
        raise SubmissionAssemblyError(
            f"{field} must be located under the workspace root."
        ) from error
    return relative.as_posix()


def _normalize_timestamp(
    value: datetime | str | None,
    field: str,
    *,
    default: str,
) -> str:
    if value is None:
        return default
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise SubmissionAssemblyError(
                f"{field} must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise SubmissionAssemblyError(
            f"{field} must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise SubmissionAssemblyError(
            f"{field} must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SubmissionAssemblyError(f"{field} must be timezone-aware.")
    return value


def _validate_identifiers(
    class_id: str, assignment_id: str, student_id: str
) -> None:
    for field, value in (
        ("class_id", class_id),
        ("assignment_id", assignment_id),
        ("student_id", student_id),
    ):
        try:
            validate_identifier(value, field)
        except IdentifierValidationError as error:
            raise SubmissionAssemblyError(str(error)) from error


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SubmissionAssemblyError(f"{field} must be a positive integer.")
    return value


def _validate_optional_positive_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _validate_positive_integer(value, field)


def _validate_json_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionAssemblyError(f"{field} must be a JSON object.")
    try:
        json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise SubmissionAssemblyError(
            f"{field} must contain only JSON-compatible values."
        ) from error


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SubmissionAssemblyError(f"{field} must be a non-empty string.")
    return value

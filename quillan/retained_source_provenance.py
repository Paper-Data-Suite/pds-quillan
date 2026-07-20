"""Pure consistency validation for one exact Core source-retention event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
import re
from typing import Final
import unicodedata

from pds_core.identifiers import validate_identifier
from pds_core.scan_routes import (
    build_retained_source_filename,
    retained_source_scan_path,
)

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CoreRetentionEventIdentity:
    retained_filename: str
    retained_relative_path: PurePosixPath
    source_scan_id: str


def validate_core_retention_event_consistency(
    *,
    source_scan_id: object,
    source_filename: object,
    source_sha256: object,
    retained_source_path: object,
    retained_source_relative_path: object,
    intake_timestamp: object,
    intake_date: object,
    workspace_root: Path | None = None,
) -> CoreRetentionEventIdentity:
    """Require all provenance fields to describe one exact Core retention event."""
    if not isinstance(source_scan_id, str):
        raise ValueError("source_scan_id must be a string.")
    validate_identifier(source_scan_id, "source_scan_id")
    if not isinstance(source_filename, str):
        raise ValueError("source_filename must be a string.")
    if any(
        unicodedata.category(character) in {"Cc", "Zl", "Zp"}
        for character in source_filename
    ):
        raise ValueError(
            "source_filename must not contain control or line-separator characters."
        )
    if not isinstance(source_sha256, str) or _SHA256.fullmatch(source_sha256) is None:
        raise ValueError("source_sha256 must be 64 lowercase hexadecimal characters.")
    if not isinstance(intake_timestamp, datetime):
        raise ValueError("intake_timestamp must be a datetime.")
    if intake_timestamp.tzinfo is None or intake_timestamp.utcoffset() is None:
        raise ValueError("intake_timestamp must be timezone-aware.")
    if isinstance(intake_date, datetime) or not isinstance(intake_date, date):
        raise ValueError("intake_date must be a date, not a datetime.")
    if not isinstance(retained_source_path, Path):
        raise ValueError("retained_source_path must be a Path.")
    if not retained_source_path.is_absolute():
        raise ValueError("retained_source_path must be absolute.")
    relative = _canonical_relative_path(retained_source_relative_path)

    expected_filename = build_retained_source_filename(
        intake_timestamp=intake_timestamp,
        original_filename=source_filename,
        sha256_hex=source_sha256,
    )
    expected_scan_id = f"scan_{Path(expected_filename).stem}"
    if retained_source_path.name != expected_filename:
        raise ValueError("retained filename contradicts the Core retention event.")
    if relative.name != expected_filename:
        raise ValueError("retained relative filename contradicts the Core event.")
    if source_scan_id != expected_scan_id:
        raise ValueError("source_scan_id contradicts the retained filename.")
    if Path(source_filename).suffix.lower() != Path(expected_filename).suffix.lower():
        raise ValueError("source and retained extensions disagree.")
    if relative.parts[2] != intake_date.isoformat():
        raise ValueError("retained date bucket contradicts intake_date.")
    if tuple(retained_source_path.parts[-len(relative.parts) :]) != relative.parts:
        raise ValueError("retained absolute and relative paths disagree.")
    if workspace_root is not None:
        if not isinstance(workspace_root, Path):
            raise ValueError("workspace_root must be a Path.")
        expected_path = retained_source_scan_path(
            workspace_root,
            intake_date=intake_date,
            retained_filename=expected_filename,
        )
        if retained_source_path != expected_path:
            raise ValueError("retained_source_path is not the canonical Core path.")
        if relative.as_posix() != expected_path.relative_to(workspace_root).as_posix():
            raise ValueError("retained_source_relative_path is not canonical.")
    return CoreRetentionEventIdentity(expected_filename, relative, expected_scan_id)


def _canonical_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("retained relative path must be nonempty POSIX text.")
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 4:
        raise ValueError("retained relative path has the wrong shape.")
    if path.parts[:2] != ("scans", "source") or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ValueError("retained relative path is not canonical.")
    if path.as_posix() != value:
        raise ValueError("retained relative path is not canonical POSIX text.")
    try:
        date.fromisoformat(path.parts[2])
    except ValueError as error:
        raise ValueError("retained relative path date bucket is invalid.") from error
    return path


__all__ = [
    "CoreRetentionEventIdentity",
    "validate_core_retention_event_consistency",
]

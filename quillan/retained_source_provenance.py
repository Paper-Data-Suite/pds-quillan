"""Pure consistency validation for one persisted Core source-retention event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Final, cast
import unicodedata

from pds_core.identifiers import validate_identifier
from pds_core.scan_routes import retained_source_scan_path

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_RETAINED_FILENAME_ENVELOPE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<timestamp>[0-9]{8}T[0-9]{12}Z)__"
    r"(?P<body>[A-Za-z0-9_-]+)__"
    r"(?P<digest>[0-9a-f]{12})"
    r"(?P<extension>\.(?:jpeg|jpg|pdf|png|tif|tiff))$"
)
_SAFE_SCAN_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff"}
)


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
    """Validate one persisted Core retention event without rerunning its writer."""
    if not isinstance(retained_source_path, Path):
        raise ValueError("retained_source_path must be a Path.")
    if not retained_source_path.is_absolute():
        raise ValueError("retained_source_path must be absolute.")

    identity = _validate_persisted_identity(
        source_scan_id=source_scan_id,
        source_filename=source_filename,
        source_sha256=source_sha256,
        retained_source_relative_path=retained_source_relative_path,
        intake_timestamp=intake_timestamp,
        intake_date=intake_date,
    )

    if retained_source_path.name != identity.retained_filename:
        raise ValueError("retained absolute and relative filenames disagree.")
    if tuple(retained_source_path.parts[-len(identity.retained_relative_path.parts) :]) != (
        identity.retained_relative_path.parts
    ):
        raise ValueError("retained absolute and relative paths disagree.")

    if workspace_root is not None:
        if not isinstance(workspace_root, Path):
            raise ValueError("workspace_root must be a Path.")
        expected_path = retained_source_scan_path(
            workspace_root,
            intake_date=cast(date, intake_date),
            retained_filename=identity.retained_filename,
        )
        if retained_source_path != expected_path:
            raise ValueError("retained_source_path is not the canonical Core path.")
        if (
            identity.retained_relative_path.as_posix()
            != expected_path.relative_to(workspace_root).as_posix()
        ):
            raise ValueError("retained_source_relative_path is not canonical.")

    return identity


def validate_serialized_core_retention_event_consistency(
    *,
    source_scan_id: object,
    source_filename: object,
    source_sha256: object,
    retained_source_relative_path: object,
    intake_timestamp: object,
    intake_date: object,
) -> CoreRetentionEventIdentity:
    """Validate serialized persisted provenance without filesystem access."""
    if not isinstance(intake_timestamp, str):
        raise ValueError("intake_timestamp must be ISO timestamp text.")
    try:
        parsed_timestamp = datetime.fromisoformat(intake_timestamp)
    except ValueError as error:
        raise ValueError(
            "intake_timestamp must be valid ISO timestamp text."
        ) from error

    if not isinstance(intake_date, str):
        raise ValueError("intake_date must be ISO date text.")
    try:
        parsed_date = date.fromisoformat(intake_date)
    except ValueError as error:
        raise ValueError("intake_date must be valid ISO date text.") from error

    return _validate_persisted_identity(
        source_scan_id=source_scan_id,
        source_filename=source_filename,
        source_sha256=source_sha256,
        retained_source_relative_path=retained_source_relative_path,
        intake_timestamp=parsed_timestamp,
        intake_date=parsed_date,
    )


def _validate_persisted_identity(
    *,
    source_scan_id: object,
    source_filename: object,
    source_sha256: object,
    retained_source_relative_path: object,
    intake_timestamp: object,
    intake_date: object,
) -> CoreRetentionEventIdentity:
    if not isinstance(source_scan_id, str):
        raise ValueError("source_scan_id must be a string.")
    validate_identifier(source_scan_id, "source_scan_id")

    validated_source_filename = _source_filename(source_filename)

    if not isinstance(source_sha256, str) or _SHA256.fullmatch(source_sha256) is None:
        raise ValueError("source_sha256 must be 64 lowercase hexadecimal characters.")

    if not isinstance(intake_timestamp, datetime):
        raise ValueError("intake_timestamp must be a datetime.")
    if intake_timestamp.tzinfo is None or intake_timestamp.utcoffset() is None:
        raise ValueError("intake_timestamp must be timezone-aware.")

    if isinstance(intake_date, datetime) or not isinstance(intake_date, date):
        raise ValueError("intake_date must be a date, not a datetime.")

    relative = _canonical_relative_path(retained_source_relative_path)
    retained_filename = relative.name

    # Delegate the stable Core filename/date safety grammar to Core, but use the
    # persisted leaf itself. Historical identity is never regenerated from
    # source_filename.
    retained_source_scan_path(
        Path("."),
        intake_date=intake_date,
        retained_filename=retained_filename,
    )

    envelope = _RETAINED_FILENAME_ENVELOPE.fullmatch(retained_filename)
    if envelope is None:
        raise ValueError("retained filename does not match the Core 0.6 envelope.")

    expected_timestamp = intake_timestamp.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    if envelope.group("timestamp") != expected_timestamp:
        raise ValueError("retained filename timestamp contradicts intake_timestamp.")

    if envelope.group("digest") != source_sha256[:12]:
        raise ValueError("retained filename digest contradicts source_sha256.")

    retained_extension = envelope.group("extension")
    if Path(validated_source_filename).suffix.lower() != retained_extension:
        raise ValueError("source and retained extensions disagree.")

    if relative.parts[2] != intake_date.isoformat():
        raise ValueError("retained date bucket contradicts intake_date.")

    expected_scan_id = f"scan_{Path(retained_filename).stem}"
    if source_scan_id != expected_scan_id:
        raise ValueError("source_scan_id contradicts the retained filename.")

    return CoreRetentionEventIdentity(
        retained_filename=retained_filename,
        retained_relative_path=relative,
        source_scan_id=source_scan_id,
    )


def _source_filename(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("source_filename must be a string.")
    if value == "":
        raise ValueError("source_filename must not be empty.")
    if value != value.strip():
        raise ValueError(
            "source_filename must not contain leading or trailing whitespace."
        )
    if (
        value in {".", ".."}
        or "\x00" in value
        or "/" in value
        or "\\" in value
        or PureWindowsPath(value).drive
        or any(
            unicodedata.category(character) in {"Cc", "Zl", "Zp"}
            for character in value
        )
    ):
        raise ValueError("source_filename must be a safe filename, not a path.")
    if Path(value).suffix.lower() not in _SAFE_SCAN_EXTENSIONS:
        raise ValueError("source_filename must use a supported scan extension.")
    return value


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
    "validate_serialized_core_retention_event_consistency",
]

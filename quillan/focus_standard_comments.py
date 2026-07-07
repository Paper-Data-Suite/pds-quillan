"""Runtime support for reusable Focus Standard comment sets."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REQUIRED_COMMENT_SET_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "comment_set_id",
        "title",
        "description",
        "standards_profile_id",
        "writing_types",
        "grade_band",
        "comments",
        "created_at",
        "updated_at",
        "module_details",
    }
)
REQUIRED_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "comment_id",
        "standard_id",
        "writing_types",
        "rating_values",
        "label",
        "text",
        "purpose",
        "student_facing",
        "active",
        "created_at",
        "updated_at",
        "source",
        "usage",
        "module_details",
    }
)
REQUIRED_SOURCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "type",
        "class_id",
        "assignment_id",
        "student_id",
        "review_path",
        "feedback_comment_id",
        "saved_at",
    }
)
REQUIRED_USAGE_FIELDS: Final[frozenset[str]] = frozenset(
    {"times_used", "last_used_at"}
)
ALLOWED_PURPOSES: Final[frozenset[str]] = frozenset(
    {
        "praise",
        "next_step",
        "clarification",
        "evidence",
        "reasoning",
        "organization",
        "style",
        "conventions",
        "revision",
        "general",
    }
)
ALLOWED_SOURCE_TYPES: Final[frozenset[str]] = frozenset(
    {"manual", "teacher_saved_from_feedback", "migration", "starter_material"}
)


class FocusStandardCommentError(ValueError):
    """Raised when reusable Focus Standard comments are missing or invalid."""


@dataclass(frozen=True, slots=True)
class FocusStandardCommentSetFile:
    """One discovered reusable Focus Standard comment set."""

    path: Path
    comment_set: dict[str, Any] | None
    error: str | None

    @property
    def is_valid(self) -> bool:
        return self.comment_set is not None and self.error is None


@dataclass(frozen=True, slots=True)
class ReusableFocusStandardComment:
    """One reusable comment match for a Focus Standard."""

    comment_set_id: str
    comment_id: str
    standard_id: str
    label: str
    text: str
    purpose: str
    rating_values: tuple[int | float, ...]
    writing_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SavedReusableFocusStandardComment:
    """Information about a reusable comment saved from feedback."""

    comment_set_id: str
    comment_id: str
    path: Path
    standard_id: str
    label: str
    text: str
    purpose: str
    created_at: str


def focus_standard_comment_set_path(
    workspace_root: str | Path, comment_set_id: str
) -> Path:
    """Return the canonical path for one reusable Focus Standard comment set."""
    normalized_id = _validate_identifier(comment_set_id, "comment_set_id")
    return _comment_sets_dir(workspace_root) / f"{normalized_id}.json"


def list_focus_standard_comment_set_files(
    workspace_root: str | Path,
) -> tuple[FocusStandardCommentSetFile, ...]:
    """List reusable Focus Standard comment set files without raising on invalid files."""
    directory = _comment_sets_dir(workspace_root)
    if not directory.is_dir():
        return ()
    files: list[FocusStandardCommentSetFile] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            files.append(FocusStandardCommentSetFile(path, load_comment_set(path), None))
        except (OSError, FocusStandardCommentError) as error:
            files.append(FocusStandardCommentSetFile(path, None, str(error)))
    return tuple(files)


def list_valid_comment_sets(
    workspace_root: str | Path,
) -> tuple[FocusStandardCommentSetFile, ...]:
    """Return valid reusable Focus Standard comment set files only."""
    return tuple(
        item for item in list_focus_standard_comment_set_files(workspace_root) if item.is_valid
    )


def load_comment_set(path: str | Path) -> dict[str, Any]:
    """Load and validate a reusable Focus Standard comment set."""
    comment_set_path = Path(path)
    try:
        with comment_set_path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise FocusStandardCommentError(
            f"Focus Standard comment set not found: {comment_set_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise FocusStandardCommentError(
            f"Focus Standard comment set is not valid JSON: {comment_set_path}"
        ) from error
    except OSError as error:
        raise FocusStandardCommentError(
            f"Could not read Focus Standard comment set {comment_set_path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise FocusStandardCommentError(
            f"Focus Standard comment set must be a JSON object: {comment_set_path}"
        )
    comment_set = cast(dict[str, Any], value)
    validate_comment_set(comment_set)
    if comment_set["comment_set_id"] != comment_set_path.stem:
        raise FocusStandardCommentError(
            "Focus Standard comment set comment_set_id is "
            f"{comment_set['comment_set_id']!r}, expected {comment_set_path.stem!r}."
        )
    return comment_set


def validate_comment_set(comment_set: dict[str, Any]) -> None:
    """Validate the reusable Focus Standard comment set contract."""
    if not isinstance(comment_set, dict):
        raise FocusStandardCommentError("Focus Standard comment set must be an object.")
    _validate_fields(comment_set, REQUIRED_COMMENT_SET_FIELDS, frozenset(), "comment set")
    _validate_exact(comment_set["schema_version"], "schema_version", "1")
    _validate_exact(comment_set["module"], "module", "quillan")
    _validate_exact(
        comment_set["record_type"],
        "record_type",
        "focus_standard_comment_set",
    )
    _validate_identifier(comment_set["comment_set_id"], "comment_set_id")
    _validate_non_empty_string(comment_set["title"], "title")
    _validate_non_empty_string(comment_set["description"], "description")
    _validate_non_empty_string(
        comment_set["standards_profile_id"], "standards_profile_id"
    )
    _validate_unique_strings(comment_set["writing_types"], "writing_types")
    if comment_set["grade_band"] is not None:
        _validate_non_empty_string(comment_set["grade_band"], "grade_band")
    seen_comment_ids: set[str] = set()
    comments = _validate_list(comment_set["comments"], "comments")
    for index, value in enumerate(comments):
        _validate_comment(value, f"comments[{index}]", seen_comment_ids)
    created_at = _validate_timestamp(comment_set["created_at"], "created_at")
    updated_at = _validate_timestamp(comment_set["updated_at"], "updated_at")
    if updated_at < created_at:
        raise FocusStandardCommentError(
            "Field 'updated_at' must not precede field 'created_at'."
        )
    _validate_object(comment_set["module_details"], "module_details")


def lookup_comments(
    workspace_root: str | Path,
    *,
    standards_profile_id: str,
    writing_type: str,
    standard_id: str,
    rating_value: int | float | None = None,
    comment_set_id: str | None = None,
) -> tuple[ReusableFocusStandardComment, ...]:
    """Find active, student-facing reusable comments compatible with an assignment."""
    matches: list[ReusableFocusStandardComment] = []
    if comment_set_id is not None:
        files = (
            FocusStandardCommentSetFile(
                focus_standard_comment_set_path(workspace_root, comment_set_id),
                load_comment_set(focus_standard_comment_set_path(workspace_root, comment_set_id)),
                None,
            ),
        )
    else:
        files = list_valid_comment_sets(workspace_root)
    for file in files:
        comment_set = file.comment_set
        if comment_set is None:
            continue
        if comment_set["standards_profile_id"] != standards_profile_id:
            continue
        set_writing_types = comment_set["writing_types"]
        if set_writing_types and writing_type not in set_writing_types:
            continue
        for comment in comment_set["comments"]:
            if not _comment_matches(
                comment,
                standard_id=standard_id,
                writing_type=writing_type,
                rating_value=rating_value,
            ):
                continue
            matches.append(
                ReusableFocusStandardComment(
                    comment_set_id=comment_set["comment_set_id"],
                    comment_id=comment["comment_id"],
                    standard_id=comment["standard_id"],
                    label=comment["label"].strip(),
                    text=comment["text"].strip(),
                    purpose=comment["purpose"],
                    rating_values=tuple(comment["rating_values"]),
                    writing_types=tuple(comment["writing_types"]),
                )
            )
    return tuple(matches)


def append_saved_comment(
    workspace_root: str | Path,
    *,
    standards_profile_id: str,
    writing_type: str,
    standard_id: str,
    label: str,
    text: str,
    purpose: str,
    rating_values: list[int | float] | None,
    source: dict[str, Any],
    created_at: datetime | str | None = None,
    comment_set_id: str | None = None,
    comment_id: str | None = None,
) -> SavedReusableFocusStandardComment:
    """Append a teacher-approved reusable comment, creating a default set if needed."""
    normalized_created_at = _normalize_timestamp(created_at)
    normalized_set_id = (
        _validate_identifier(comment_set_id, "comment_set_id")
        if comment_set_id is not None
        else _default_comment_set_id(standards_profile_id, writing_type)
    )
    normalized_comment_id = (
        _validate_identifier(comment_id, "comment_id")
        if comment_id is not None
        else suggest_identifier(label)
    )
    normalized_label = _normalize_required_string(label, "label")
    normalized_text = _normalize_required_string(text, "text")
    normalized_purpose = _validate_allowed(purpose, "purpose", ALLOWED_PURPOSES)
    normalized_rating_values = _normalize_unique_numbers(
        rating_values or [], "rating_values"
    )
    path = focus_standard_comment_set_path(workspace_root, normalized_set_id)
    if path.exists():
        comment_set = load_comment_set(path)
        if comment_set["standards_profile_id"] != standards_profile_id:
            raise FocusStandardCommentError(
                "Existing Focus Standard comment set standards_profile_id does not "
                f"match {standards_profile_id!r}."
            )
        if comment_set["writing_types"] and writing_type not in comment_set["writing_types"]:
            raise FocusStandardCommentError(
                "Existing Focus Standard comment set does not include writing_type "
                f"{writing_type!r}."
            )
    else:
        comment_set = _build_default_comment_set(
            comment_set_id=normalized_set_id,
            standards_profile_id=standards_profile_id,
            writing_type=writing_type,
            created_at=normalized_created_at,
        )

    existing_ids = {comment["comment_id"] for comment in comment_set["comments"]}
    normalized_comment_id = _unique_identifier(normalized_comment_id, existing_ids)
    comment = {
        "comment_id": normalized_comment_id,
        "standard_id": _normalize_required_string(standard_id, "standard_id"),
        "writing_types": [writing_type],
        "rating_values": normalized_rating_values,
        "label": normalized_label,
        "text": normalized_text,
        "purpose": normalized_purpose,
        "student_facing": True,
        "active": True,
        "created_at": normalized_created_at,
        "updated_at": normalized_created_at,
        "source": copy.deepcopy(source),
        "usage": {"times_used": 0, "last_used_at": None},
        "module_details": {},
    }
    comment_set["comments"].append(comment)
    if not comment_set["writing_types"]:
        comment_set["writing_types"] = [writing_type]
    elif writing_type not in comment_set["writing_types"]:
        comment_set["writing_types"].append(writing_type)
    comment_set["updated_at"] = normalized_created_at
    write_comment_set(workspace_root, comment_set, overwrite=path.exists())
    return SavedReusableFocusStandardComment(
        comment_set_id=normalized_set_id,
        comment_id=normalized_comment_id,
        path=path,
        standard_id=standard_id,
        label=normalized_label,
        text=normalized_text,
        purpose=normalized_purpose,
        created_at=normalized_created_at,
    )


def increment_usage(
    workspace_root: str | Path,
    *,
    comment_set_id: str,
    comment_id: str,
    used_at: datetime | str | None = None,
) -> None:
    """Increment usage metadata after a teacher selects a reusable comment."""
    normalized_used_at = _normalize_timestamp(used_at)
    path = focus_standard_comment_set_path(workspace_root, comment_set_id)
    comment_set = load_comment_set(path)
    for comment in comment_set["comments"]:
        if comment["comment_id"] == comment_id:
            comment["usage"]["times_used"] += 1
            comment["usage"]["last_used_at"] = normalized_used_at
            comment["updated_at"] = normalized_used_at
            comment_set["updated_at"] = normalized_used_at
            write_comment_set(workspace_root, comment_set, overwrite=True)
            return
    raise FocusStandardCommentError(
        f"Reusable Focus Standard comment not found: {comment_id!r}."
    )


def write_comment_set(
    workspace_root: str | Path,
    comment_set: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and safely write a reusable Focus Standard comment set."""
    validate_comment_set(comment_set)
    path = focus_standard_comment_set_path(workspace_root, comment_set["comment_set_id"])
    directory = _comment_sets_dir(workspace_root).resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        resolved_path.relative_to(directory)
    except ValueError as error:
        raise FocusStandardCommentError(
            f"Focus Standard comment set path escapes shared directory: {path}"
        ) from error
    if path.exists() and not overwrite:
        raise FocusStandardCommentError(
            f"Focus Standard comment set already exists: {path}"
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FocusStandardCommentError(
            f"Could not create Focus Standard comment directory {path.parent}: {error}"
        ) from error
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(comment_set, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise FocusStandardCommentError(
            f"Focus Standard comment set already exists: {path}"
        ) from error
    except (OSError, TypeError, ValueError) as error:
        raise FocusStandardCommentError(
            f"Could not write Focus Standard comment set {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return path


def suggest_identifier(label: str) -> str:
    """Suggest a reusable comment identifier from teacher-facing text."""
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_label.strip())
    suggestion = suggestion.strip("_-").lower()
    return suggestion or "focus_standard_comment"


def _comment_sets_dir(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "shared" / "focus_standard_comments"


def _comment_matches(
    comment: dict[str, Any],
    *,
    standard_id: str,
    writing_type: str,
    rating_value: int | float | None,
) -> bool:
    if comment["standard_id"] != standard_id:
        return False
    if not comment["active"] or not comment["student_facing"]:
        return False
    if comment["writing_types"] and writing_type not in comment["writing_types"]:
        return False
    if rating_value is not None and comment["rating_values"]:
        return rating_value in comment["rating_values"]
    return True


def _validate_comment(
    value: Any, context: str, seen_comment_ids: set[str]
) -> None:
    comment = _validate_record(value, context)
    _validate_fields(comment, REQUIRED_COMMENT_FIELDS, frozenset(), context)
    comment_id = _validate_identifier(comment["comment_id"], f"{context}.comment_id")
    if comment_id in seen_comment_ids:
        raise FocusStandardCommentError(f"Duplicate comment_id '{comment_id}'.")
    seen_comment_ids.add(comment_id)
    _validate_non_empty_string(comment["standard_id"], f"{context}.standard_id")
    _validate_unique_strings(comment["writing_types"], f"{context}.writing_types")
    _normalize_unique_numbers(comment["rating_values"], f"{context}.rating_values")
    _validate_non_empty_string(comment["label"], f"{context}.label")
    _validate_non_empty_string(comment["text"], f"{context}.text")
    _validate_allowed(comment["purpose"], f"{context}.purpose", ALLOWED_PURPOSES)
    _validate_boolean(comment["student_facing"], f"{context}.student_facing")
    _validate_boolean(comment["active"], f"{context}.active")
    created_at = _validate_timestamp(comment["created_at"], f"{context}.created_at")
    updated_at = _validate_timestamp(comment["updated_at"], f"{context}.updated_at")
    if updated_at < created_at:
        raise FocusStandardCommentError(
            f"Field '{context}.updated_at' must not precede field '{context}.created_at'."
        )
    _validate_source(comment["source"], f"{context}.source")
    _validate_usage(comment["usage"], f"{context}.usage")
    _validate_object(comment["module_details"], f"{context}.module_details")


def _validate_source(value: Any, context: str) -> None:
    source = _validate_record(value, context)
    _validate_fields(source, REQUIRED_SOURCE_FIELDS, frozenset(), context)
    source_type = _validate_allowed(source["type"], f"{context}.type", ALLOWED_SOURCE_TYPES)
    _validate_timestamp(source["saved_at"], f"{context}.saved_at")
    for field in ("class_id", "assignment_id", "student_id", "feedback_comment_id"):
        if source[field] is not None:
            _validate_non_empty_string(source[field], f"{context}.{field}")
    if source["review_path"] is not None:
        _validate_workspace_relative_path(source["review_path"], f"{context}.review_path")
    if source_type == "manual":
        for field in ("class_id", "assignment_id", "student_id", "review_path", "feedback_comment_id"):
            if source[field] is not None:
                raise FocusStandardCommentError(
                    f"Field '{context}.{field}' must be null for manual sources."
                )
    if source_type == "teacher_saved_from_feedback":
        for field in ("class_id", "assignment_id", "student_id", "review_path", "feedback_comment_id"):
            _validate_non_empty_string(source[field], f"{context}.{field}")


def _validate_usage(value: Any, context: str) -> None:
    usage = _validate_record(value, context)
    _validate_fields(usage, REQUIRED_USAGE_FIELDS, frozenset(), context)
    times_used = usage["times_used"]
    if isinstance(times_used, bool) or not isinstance(times_used, int) or times_used < 0:
        raise FocusStandardCommentError(
            f"Field '{context}.times_used' must be a non-negative integer."
        )
    if usage["last_used_at"] is not None:
        _validate_timestamp(usage["last_used_at"], f"{context}.last_used_at")
    if times_used == 0 and usage["last_used_at"] is not None:
        raise FocusStandardCommentError(
            f"Field '{context}.last_used_at' must be null when times_used is 0."
        )
    if times_used > 0 and usage["last_used_at"] is None:
        raise FocusStandardCommentError(
            f"Field '{context}.last_used_at' must not be null when times_used is greater than 0."
        )


def _build_default_comment_set(
    *,
    comment_set_id: str,
    standards_profile_id: str,
    writing_type: str,
    created_at: str,
) -> dict[str, Any]:
    title = f"{standards_profile_id} {writing_type} Focus Standard Comments"
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "focus_standard_comment_set",
        "comment_set_id": comment_set_id,
        "title": title,
        "description": (
            "Reusable teacher-authored Focus Standard comments saved from "
            "Quillan feedback composition."
        ),
        "standards_profile_id": standards_profile_id,
        "writing_types": [writing_type],
        "grade_band": None,
        "comments": [],
        "created_at": created_at,
        "updated_at": created_at,
        "module_details": {},
    }


def _default_comment_set_id(standards_profile_id: str, writing_type: str) -> str:
    return _validate_identifier(
        suggest_identifier(f"{standards_profile_id}_{writing_type}_focus_comments"),
        "comment_set_id",
    )


def _unique_identifier(identifier: str, existing: set[str]) -> str:
    candidate = identifier
    counter = 2
    while candidate in existing:
        candidate = f"{identifier}_{counter}"
        counter += 1
    return _validate_identifier(candidate, "comment_id")


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise FocusStandardCommentError("timestamp datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise FocusStandardCommentError(
            "timestamp must be a timezone-aware datetime or ISO 8601 string."
        )
    _validate_timestamp(value, "timestamp")
    return value


def _normalize_required_string(value: Any, field: str) -> str:
    return _validate_non_empty_string(value, field).strip()


def _normalize_unique_numbers(value: Any, field: str) -> list[int | float]:
    values = _validate_list(value, field)
    seen: set[int | float] = set()
    normalized: list[int | float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise FocusStandardCommentError(
                f"Field '{field}' must contain finite numbers."
            )
        if item != item or item in {float("inf"), float("-inf")}:
            raise FocusStandardCommentError(
                f"Field '{field}' must contain finite numbers."
            )
        if item in seen:
            raise FocusStandardCommentError(f"Field '{field}' contains duplicate {item!r}.")
        seen.add(item)
        normalized.append(item)
    return normalized


def _validate_identifier(value: Any, field: str) -> str:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise FocusStandardCommentError(str(error)) from error
    return cast(str, value)


def _validate_unique_strings(value: Any, field: str) -> list[str]:
    values = _validate_list(value, field)
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = _validate_non_empty_string(item, field)
        if text in seen:
            raise FocusStandardCommentError(f"Field '{field}' contains duplicate {text!r}.")
        seen.add(text)
        result.append(text)
    return result


def _validate_workspace_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FocusStandardCommentError(
            f"Field '{field}' must be a non-empty workspace-relative path string."
        )
    if "\0" in value:
        raise FocusStandardCommentError(f"Field '{field}' must not contain null bytes.")
    variants = (PurePosixPath(value), PureWindowsPath(value))
    if any(path.anchor or path.drive for path in variants):
        raise FocusStandardCommentError(f"Field '{field}' must be workspace-relative.")
    components = re.split(r"[\\/]", value)
    if "." in components or ".." in components:
        raise FocusStandardCommentError(
            f"Field '{field}' must not contain '.' or '..' path components."
        )


def _validate_fields(
    data: dict[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
    context: str,
) -> None:
    missing = required - data.keys()
    if missing:
        raise FocusStandardCommentError(
            f"Missing required field '{sorted(missing)[0]}' in {context}."
        )
    unknown = data.keys() - required - optional
    if unknown:
        raise FocusStandardCommentError(
            f"Unknown field '{sorted(unknown)[0]}' in {context}."
        )


def _validate_record(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FocusStandardCommentError(f"{context} must be an object.")
    return cast(dict[str, Any], value)


def _validate_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise FocusStandardCommentError(f"Field '{field}' must be a list.")
    return value


def _validate_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise FocusStandardCommentError(f"Field '{field}' must be an object.")


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FocusStandardCommentError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise FocusStandardCommentError(f"Field '{field}' must be a boolean.")
    return value


def _validate_exact(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise FocusStandardCommentError(
            f"Field '{field}' must be the string '{expected}'."
        )


def _validate_allowed(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise FocusStandardCommentError(
            f"Invalid {field} {value!r}. Allowed values: {allowed}."
        )
    return value


def _validate_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise FocusStandardCommentError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise FocusStandardCommentError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FocusStandardCommentError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return parsed

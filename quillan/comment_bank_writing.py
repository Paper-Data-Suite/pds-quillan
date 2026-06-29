"""Construction, listing, and safe writes for Quillan comment banks."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.comment_banks import (
    CommentBankError,
    comment_bank_path,
    load_comment_bank,
    validate_comment_bank,
)


@dataclass(frozen=True)
class CommentBankFile:
    """One discovered comment bank file and its validation state."""

    path: Path
    bank: dict[str, Any] | None
    error: str | None

    @property
    def is_valid(self) -> bool:
        return self.bank is not None and self.error is None


def current_timestamp() -> str:
    """Return a timezone-aware ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def suggest_identifier(label: str) -> str:
    """Suggest a shared identifier from teacher-facing text."""
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_label.strip())
    suggestion = suggestion.strip("_-").lower()
    return suggestion or "comment_bank"


def parse_comma_separated_values(value: str) -> list[str]:
    """Return trimmed nonblank values from comma-separated input."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_comment_category(
    *,
    category_id: str,
    label: str,
    description: str = "",
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Build and validate one category record."""
    validate_identifier(category_id, "category_id")
    if not label.strip():
        raise CommentBankError("Category label is required.")
    category: dict[str, Any] = {
        "category_id": category_id,
        "label": label.strip(),
    }
    if description.strip():
        category["description"] = description.strip()
    if sort_order is not None:
        category["sort_order"] = sort_order
    return category


def build_comment(
    *,
    comment_id: str,
    label: str,
    text: str,
    category_id: str,
    polarity: str,
    include_in_feedback_default: bool = True,
    student_facing: bool = True,
    module_details: Mapping[str, Any] | None = None,
    optional_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one comment record."""
    validate_identifier(comment_id, "comment_id")
    validate_identifier(category_id, "category_id")
    if not label.strip():
        raise CommentBankError("Comment label is required.")
    if not text.strip():
        raise CommentBankError("Student-facing feedback text is required.")
    comment: dict[str, Any] = {
        "comment_id": comment_id,
        "label": label.strip(),
        "text": text.strip(),
        "category_id": category_id,
        "polarity": polarity,
        "include_in_feedback_default": include_in_feedback_default,
        "student_facing": student_facing,
        "module_details": dict(module_details or {}),
    }
    if optional_metadata:
        comment.update(dict(optional_metadata))
    return comment


def build_comment_bank(
    *,
    bank_id: str,
    title: str,
    description: str,
    writing_types: Sequence[str],
    categories: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
    created_at: str | None = None,
    updated_at: str | None = None,
    module_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a version 1 Quillan shared comment bank."""
    timestamp = current_timestamp()
    bank: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "comment_bank",
        "bank_id": bank_id,
        "title": title.strip(),
        "description": description.strip(),
        "scope": "shared",
        "writing_types": list(writing_types),
        "categories": [dict(category) for category in categories],
        "comments": [dict(comment) for comment in comments],
        "created_at": created_at or timestamp,
        "updated_at": updated_at or timestamp,
        "module_details": dict(module_details or {}),
    }
    validate_comment_bank(bank)
    return bank


def list_comment_bank_files(workspace_root: str | Path) -> tuple[CommentBankFile, ...]:
    """List shared comment-bank files without raising on invalid files."""
    directory = Path(workspace_root) / "shared" / "comment_banks"
    if not directory.is_dir():
        return ()
    files: list[CommentBankFile] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            files.append(CommentBankFile(path, load_comment_bank(path), None))
        except (OSError, CommentBankError) as error:
            files.append(CommentBankFile(path, None, str(error)))
    return tuple(files)


def list_valid_comment_banks(
    workspace_root: str | Path,
) -> tuple[CommentBankFile, ...]:
    """Return valid shared comment-bank files only."""
    return tuple(
        item for item in list_comment_bank_files(workspace_root) if item.is_valid
    )


def summarize_comment_bank(bank: Mapping[str, Any], path: str | Path) -> str:
    """Return a concise teacher-facing summary for one bank."""
    writing_types = ", ".join(str(item) for item in bank["writing_types"])
    return "\n".join(
        [
            f"Bank ID: {bank['bank_id']}",
            f"Title: {bank['title']}",
            f"Description: {bank['description']}",
            f"Scope: {bank['scope']}",
            f"Writing assignment types: {writing_types}",
            f"Categories: {len(bank['categories'])}",
            f"Comments: {len(bank['comments'])}",
            f"Path: {Path(path)}",
        ]
    )


def write_comment_bank(
    workspace_root: str | Path,
    bank: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and atomically write a shared comment bank."""
    bank_data = dict(bank)
    validate_comment_bank(bank_data)
    bank_id = str(bank_data["bank_id"])
    path = comment_bank_path(workspace_root, bank_id)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Comment bank already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(bank_data, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def touch_updated_at(bank: Mapping[str, Any]) -> dict[str, Any]:
    """Return a mutable copy with a refreshed updated_at value."""
    updated = dict(bank)
    updated["updated_at"] = current_timestamp()
    return updated


def ensure_unique_identifier(identifier: str, existing: set[str], field: str) -> None:
    """Validate an identifier and reject duplicates."""
    try:
        validate_identifier(identifier, field)
    except IdentifierValidationError as error:
        raise CommentBankError(str(error)) from error
    if identifier in existing:
        raise CommentBankError(f"Duplicate {field} '{identifier}'.")

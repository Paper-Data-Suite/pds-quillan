"""Construction, listing, and safe writes for Quillan tag banks."""

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

from quillan.tag_banks import (
    TagBankError,
    load_tag_bank,
    tag_bank_path,
    validate_tag_bank,
)


@dataclass(frozen=True)
class TagBankFile:
    """One discovered tag bank file and its validation state."""

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
    return suggestion or "tag_bank"


def parse_comma_separated_values(value: str) -> list[str]:
    """Return trimmed nonblank values from comma-separated input."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_tag_category(
    *,
    category_id: str,
    label: str,
    description: str = "",
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Build one category record."""
    validate_identifier(category_id, "category_id")
    if not label.strip():
        raise TagBankError("Category label is required.")
    category: dict[str, Any] = {
        "category_id": category_id,
        "label": label.strip(),
        "module_details": {},
    }
    if description.strip():
        category["description"] = description.strip()
    if sort_order is not None:
        category["sort_order"] = sort_order
    return category


def build_tag_template(
    *,
    tag_template_id: str,
    label: str,
    category_id: str,
    polarity: str,
    module_details: Mapping[str, Any] | None = None,
    optional_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one reusable tag template record."""
    validate_identifier(tag_template_id, "tag_template_id")
    validate_identifier(category_id, "category_id")
    if not label.strip():
        raise TagBankError("Tag label is required.")
    tag: dict[str, Any] = {
        "tag_template_id": tag_template_id,
        "label": label.strip(),
        "category_id": category_id,
        "polarity": polarity,
        "module_details": dict(module_details or {}),
    }
    if optional_metadata:
        tag.update(dict(optional_metadata))
    return tag


def build_tag_bank(
    *,
    tag_bank_id: str,
    title: str,
    description: str,
    writing_types: Sequence[str],
    categories: Sequence[Mapping[str, Any]],
    tags: Sequence[Mapping[str, Any]],
    created_at: str | None = None,
    updated_at: str | None = None,
    module_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a version 1 Quillan shared tag bank."""
    timestamp = current_timestamp()
    bank: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "tag_bank",
        "tag_bank_id": tag_bank_id,
        "title": title.strip(),
        "description": description.strip(),
        "scope": "shared",
        "writing_types": list(writing_types),
        "categories": [dict(category) for category in categories],
        "tags": [dict(tag) for tag in tags],
        "created_at": created_at or timestamp,
        "updated_at": updated_at or timestamp,
        "module_details": dict(module_details or {}),
    }
    validate_tag_bank(bank)
    return bank


def list_tag_bank_files(workspace_root: str | Path) -> tuple[TagBankFile, ...]:
    """List shared tag-bank files without raising on invalid files."""
    directory = Path(workspace_root) / "shared" / "tag_banks"
    if not directory.is_dir():
        return ()
    files: list[TagBankFile] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            files.append(TagBankFile(path, load_tag_bank(path), None))
        except (OSError, TagBankError) as error:
            files.append(TagBankFile(path, None, str(error)))
    return tuple(files)


def list_valid_tag_banks(workspace_root: str | Path) -> tuple[TagBankFile, ...]:
    """Return valid shared tag-bank files only."""
    return tuple(item for item in list_tag_bank_files(workspace_root) if item.is_valid)


def summarize_tag_bank(bank: Mapping[str, Any], path: str | Path) -> str:
    """Return a concise teacher-facing summary for one bank."""
    writing_types = ", ".join(str(item) for item in bank["writing_types"])
    return "\n".join(
        [
            f"Tag Bank ID: {bank['tag_bank_id']}",
            f"Title: {bank['title']}",
            f"Description: {bank['description']}",
            f"Scope: {bank['scope']}",
            f"Writing types: {writing_types}",
            f"Categories: {len(bank['categories'])}",
            f"Tags: {len(bank['tags'])}",
            f"Path: {Path(path)}",
        ]
    )


def write_tag_bank(
    workspace_root: str | Path,
    bank: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and atomically write a shared tag bank."""
    bank_data = dict(bank)
    validate_tag_bank(bank_data)
    bank_id = str(bank_data["tag_bank_id"])
    path = tag_bank_path(workspace_root, bank_id)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Tag bank already exists: {path}")
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
        raise TagBankError(str(error)) from error
    if identifier in existing:
        raise TagBankError(f"Duplicate {field} '{identifier}'.")

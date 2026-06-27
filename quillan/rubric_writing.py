"""Construction, listing, and safe writes for Quillan rubrics."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.rubrics import (
    RubricError,
    RubricFile,
    rubric_path,
    validate_rubric,
)


def current_timestamp() -> str:
    """Return a timezone-aware ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def suggest_identifier(label: str) -> str:
    """Suggest a shared identifier from teacher-facing text."""
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_label.strip())
    suggestion = suggestion.strip("_-").lower()
    return suggestion or "rubric"


def parse_comma_separated_values(value: str) -> list[str]:
    """Return trimmed nonblank values from comma-separated input."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_rubric_level(
    *,
    score: int | float,
    label: str,
    description: str = "",
    student_facing_feedback: str = "",
    teacher_note: str = "",
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Build one rubric level record."""
    if not label.strip():
        raise RubricError("Level label is required.")
    level: dict[str, Any] = {
        "score": score,
        "label": label.strip(),
        "module_details": {},
    }
    if description.strip():
        level["description"] = description.strip()
    if student_facing_feedback.strip():
        level["student_facing_feedback"] = student_facing_feedback.strip()
    if teacher_note.strip():
        level["teacher_note"] = teacher_note.strip()
    if sort_order is not None:
        level["sort_order"] = sort_order
    return level


def build_rubric_criterion(
    *,
    criterion_id: str,
    label: str,
    max_score: int | float,
    scale: str,
    levels: Sequence[Mapping[str, Any]],
    description: str = "",
    standard_ids: Sequence[str] | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Build one rubric criterion record."""
    validate_identifier(criterion_id, "criterion_id")
    if not label.strip():
        raise RubricError("Criterion label is required.")
    criterion: dict[str, Any] = {
        "criterion_id": criterion_id,
        "label": label.strip(),
        "max_score": max_score,
        "scale": scale.strip(),
        "levels": [dict(level) for level in levels],
        "module_details": {},
    }
    if description.strip():
        criterion["description"] = description.strip()
    if standard_ids:
        criterion["standard_ids"] = list(standard_ids)
    if sort_order is not None:
        criterion["sort_order"] = sort_order
    return criterion


def build_rubric(
    *,
    rubric_id: str,
    title: str,
    description: str,
    writing_types: Sequence[str],
    criteria: Sequence[Mapping[str, Any]],
    created_at: str | None = None,
    updated_at: str | None = None,
    module_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a version 1 Quillan shared rubric."""
    timestamp = current_timestamp()
    rubric: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "rubric",
        "rubric_id": rubric_id,
        "title": title.strip(),
        "description": description.strip(),
        "scope": "shared",
        "writing_types": list(writing_types),
        "criteria": [dict(criterion) for criterion in criteria],
        "created_at": created_at or timestamp,
        "updated_at": updated_at or timestamp,
        "module_details": dict(module_details or {}),
    }
    validate_rubric(rubric)
    return rubric


def list_rubric_files(workspace_root: str | Path) -> tuple[RubricFile, ...]:
    """List shared rubric files without raising on invalid files."""
    from quillan.rubrics import list_rubric_files as _list_rubric_files

    return _list_rubric_files(workspace_root)


def list_valid_rubrics(workspace_root: str | Path) -> tuple[RubricFile, ...]:
    """Return valid shared rubric files only."""
    from quillan.rubrics import list_valid_rubrics as _list_valid_rubrics

    return _list_valid_rubrics(workspace_root)


def summarize_rubric(rubric: Mapping[str, Any], path: str | Path) -> str:
    """Return a concise teacher-facing summary for one rubric."""
    criteria = rubric["criteria"]
    level_count = sum(len(item["levels"]) for item in criteria)
    writing_types = ", ".join(str(item) for item in rubric["writing_types"])
    return "\n".join(
        [
            f"Rubric ID: {rubric['rubric_id']}",
            f"Title: {rubric['title']}",
            f"Description: {rubric['description']}",
            f"Scope: {rubric['scope']}",
            f"Writing types: {writing_types}",
            f"Criteria: {len(criteria)}",
            f"Levels: {level_count}",
            f"Path: {Path(path)}",
        ]
    )


def write_rubric(
    workspace_root: str | Path,
    rubric: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and atomically write a shared rubric."""
    rubric_data = dict(rubric)
    validate_rubric(rubric_data)
    rubric_id = str(rubric_data["rubric_id"])
    path = rubric_path(workspace_root, rubric_id)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Rubric already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(rubric_data, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def touch_updated_at(rubric: Mapping[str, Any]) -> dict[str, Any]:
    """Return a mutable copy with a refreshed updated_at value."""
    updated = dict(rubric)
    updated["updated_at"] = current_timestamp()
    return updated


def ensure_unique_identifier(identifier: str, existing: set[str], field: str) -> None:
    """Validate an identifier and reject duplicates."""
    try:
        validate_identifier(identifier, field)
    except IdentifierValidationError as error:
        raise RubricError(str(error)) from error
    if identifier in existing:
        raise RubricError(f"Duplicate {field} '{identifier}'.")

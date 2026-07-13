"""Read-oriented management services for reusable Focus Standard comments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.focus_standard_comments import (
    FocusStandardCommentError,
    append_saved_comment,
    comment_matches_compatibility,
    focus_standard_comment_set_path,
    list_focus_standard_comment_set_files,
    load_comment_set,
)


@dataclass(frozen=True, slots=True)
class ReusableCommentSource:
    type: str
    class_id: str | None
    assignment_id: str | None
    student_id: str | None
    review_path: str | None
    feedback_comment_id: str | None
    saved_at: str


@dataclass(frozen=True, slots=True)
class ReusableCommentStatus:
    comment_set_id: str
    comment_set_title: str
    standards_profile_id: str
    comment_id: str
    standard_id: str
    label: str
    text: str
    purpose: str
    writing_types: tuple[str, ...]
    rating_values: tuple[int | float, ...]
    student_facing: bool
    active: bool
    teacher_tags: tuple[str, ...]
    source: ReusableCommentSource
    times_used: int
    last_used_at: str | None
    created_at: str
    updated_at: str
    module_details: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class ReusableCommentSetStatus:
    comment_set_id: str
    title: str
    description: str
    standards_profile_id: str
    writing_types: tuple[str, ...]
    grade_band: str | None
    created_at: str
    updated_at: str
    module_details: str
    relative_path: str
    comments: tuple[ReusableCommentStatus, ...]


@dataclass(frozen=True, slots=True)
class InvalidReusableCommentSet:
    relative_path: str
    error: str


@dataclass(frozen=True, slots=True)
class ReusableCommentInventory:
    comments: tuple[ReusableCommentStatus, ...]
    invalid_files: tuple[InvalidReusableCommentSet, ...]


@dataclass(frozen=True, slots=True)
class CreatedManualReusableComment:
    comment_set_id: str
    comment_id: str
    set_was_created: bool
    standards_profile_id: str
    writing_type: str
    standard_id: str
    label: str
    purpose: str
    rating_values: tuple[int | float, ...]
    teacher_tags: tuple[str, ...]
    active: bool
    student_facing: bool
    times_used: int
    relative_path: str
    created_at: str


def list_reusable_comments(
    workspace_root: str | Path,
    *,
    standards_profile_id: str | None = None,
    writing_type: str | None = None,
    standard_id: str | None = None,
    rating_value: int | float | None = None,
) -> ReusableCommentInventory:
    """List matching comments while retaining invalid-file diagnostics."""
    root = Path(workspace_root)
    matches: list[ReusableCommentStatus] = []
    invalid: list[InvalidReusableCommentSet] = []
    for discovered in list_focus_standard_comment_set_files(root):
        if not discovered.is_valid:
            invalid.append(
                InvalidReusableCommentSet(
                    _relative_path(discovered.path, root),
                    discovered.error or "Unknown validation error.",
                )
            )
            continue
        comment_set = discovered.comment_set
        if comment_set is None:
            continue
        for comment in comment_set["comments"]:
            if comment_matches_compatibility(
                comment_set,
                comment,
                standards_profile_id=standards_profile_id,
                writing_type=writing_type,
                standard_id=standard_id,
                rating_value=rating_value,
            ):
                matches.append(_comment_status(comment_set, comment, discovered.path, root))
    return ReusableCommentInventory(tuple(matches), tuple(invalid))


def show_reusable_comment_set(
    workspace_root: str | Path, comment_set_id: str
) -> ReusableCommentSetStatus:
    """Load one canonical reusable comment set for complete inspection."""
    root = Path(workspace_root)
    path = focus_standard_comment_set_path(root, comment_set_id)
    data = load_comment_set(path)
    return ReusableCommentSetStatus(
        comment_set_id=data["comment_set_id"],
        title=data["title"],
        description=data["description"],
        standards_profile_id=data["standards_profile_id"],
        writing_types=tuple(data["writing_types"]),
        grade_band=data["grade_band"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        module_details=_metadata(data["module_details"]),
        relative_path=_relative_path(path, root),
        comments=tuple(
            _comment_status(data, comment, path, root) for comment in data["comments"]
        ),
    )


def create_manual_reusable_comment(
    workspace_root: str | Path,
    *,
    comment_set_id: str,
    standards_profile_id: str,
    writing_type: str,
    standard_id: str,
    label: str,
    text: str,
    purpose: str = "general",
    rating_values: list[int | float] | None = None,
    teacher_tags: list[str] | None = None,
    created_at: datetime | str | None = None,
) -> CreatedManualReusableComment:
    """Create one manual comment through the canonical append service."""
    root = Path(workspace_root)
    path = focus_standard_comment_set_path(root, comment_set_id)
    set_was_created = not path.exists()
    timestamp: datetime | str = (
        datetime.now(timezone.utc) if created_at is None else created_at
    )
    saved = append_saved_comment(
        root,
        comment_set_id=comment_set_id,
        standards_profile_id=standards_profile_id,
        writing_type=writing_type,
        standard_id=standard_id,
        label=label,
        text=text,
        purpose=purpose,
        rating_values=rating_values,
        teacher_tags=teacher_tags,
        created_at=timestamp,
        source={
            "type": "manual",
            "class_id": None,
            "assignment_id": None,
            "student_id": None,
            "review_path": None,
            "feedback_comment_id": None,
            "saved_at": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        },
    )
    data = load_comment_set(saved.path)
    comment = next(item for item in data["comments"] if item["comment_id"] == saved.comment_id)
    tags = comment["module_details"].get("teacher_tags", [])
    return CreatedManualReusableComment(
        comment_set_id=saved.comment_set_id,
        comment_id=saved.comment_id,
        set_was_created=set_was_created,
        standards_profile_id=data["standards_profile_id"],
        writing_type=comment["writing_types"][0],
        standard_id=comment["standard_id"],
        label=comment["label"],
        purpose=comment["purpose"],
        rating_values=tuple(comment["rating_values"]),
        teacher_tags=tuple(tags),
        active=comment["active"],
        student_facing=comment["student_facing"],
        times_used=comment["usage"]["times_used"],
        relative_path=_relative_path(saved.path, root),
        created_at=comment["created_at"],
    )


def _comment_status(
    comment_set: dict[str, Any], comment: dict[str, Any], path: Path, root: Path
) -> ReusableCommentStatus:
    source = comment["source"]
    return ReusableCommentStatus(
        comment_set_id=comment_set["comment_set_id"],
        comment_set_title=comment_set["title"],
        standards_profile_id=comment_set["standards_profile_id"],
        comment_id=comment["comment_id"],
        standard_id=comment["standard_id"],
        label=comment["label"],
        text=comment["text"],
        purpose=comment["purpose"],
        writing_types=tuple(comment["writing_types"]),
        rating_values=tuple(comment["rating_values"]),
        student_facing=comment["student_facing"],
        active=comment["active"],
        teacher_tags=tuple(comment["module_details"].get("teacher_tags", [])),
        source=ReusableCommentSource(**source),
        times_used=comment["usage"]["times_used"],
        last_used_at=comment["usage"]["last_used_at"],
        created_at=comment["created_at"],
        updated_at=comment["updated_at"],
        module_details=_metadata(comment["module_details"]),
        relative_path=_relative_path(path, root),
    )


def _metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value else "none"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError as error:
        raise FocusStandardCommentError(
            f"Comment set path is outside the active workspace: {path}"
        ) from error

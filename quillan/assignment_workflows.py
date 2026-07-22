"""Teacher-facing workflows for Quillan writing assignment configs."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeVar

from pds_core.classes import ClassFolder, list_class_folders
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import StandardsReadError, StandardsValidationError
from pds_core.standards_selection import (
    StandardSelectionItem,
    list_profiles_for_selection,
    list_standards_for_profile_selection,
    load_standards_for_selection,
)
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignments import (
    AssignmentConfigError,
    validate_assignment_config,
)
from quillan.atomic_record_io import (
    AtomicRecordDurabilityError,
    create_exclusive_record,
    revision_guarded_update,
)
from quillan.record_context import (
    LoadedJsonRecord,
    canonical_workspace_root,
    load_quillan_assignment_context,
)
from quillan.assignment_picker import prompt_assignment_choice
from quillan.work_paths import (
    QuillanWorkPathError,
    initialize_managed_work_layout,
    preflight_managed_work_layout,
    preflight_work_file_destination,
    quillan_work_paths,
)

_NUMERIC_REQUIREMENTS = (
    "paragraphs_min",
    "paragraphs_max",
    "word_count_min",
    "word_count_max",
)
_DEFAULT_REVIEW_UNIT = {
    "type": "paragraph",
    "singular_label": "paragraph",
    "plural_label": "paragraphs",
}
_DEFAULT_RATING_SCALE = {
    "scale_id": "standards_4_level",
    "levels": [
        {
            "value": 1,
            "label": "Developing",
            "description": (
                "The work shows limited or emerging evidence of the standard."
            ),
        },
        {
            "value": 2,
            "label": "Approaching",
            "description": (
                "The work shows partial evidence of the standard but is uneven, "
                "general, or incomplete."
            ),
        },
        {
            "value": 3,
            "label": "Meeting",
            "description": "The work shows clear and sufficient evidence of the standard.",
        },
        {
            "value": 4,
            "label": "Exceeding",
            "description": (
                "The work shows especially strong, precise, or sophisticated "
                "evidence of the standard."
            ),
        },
    ],
}
_T = TypeVar("_T")


class AssignmentBatchWriteError(AssignmentConfigError):
    """A multi-class write failed, with conservative compensation details."""

    def __init__(
        self,
        message: str,
        *,
        possibly_durable_paths: tuple[Path, ...],
        rollback_diagnostics: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.possibly_durable_paths = possibly_durable_paths
        self.rollback_diagnostics = rollback_diagnostics


@dataclass(slots=True)
class _AssignmentWriteJournalEntry:
    path: Path
    original: LoadedJsonRecord | None
    replacement_bytes: bytes
    status: Literal["pending", "unchanged", "created", "updated"] = "pending"


def suggest_assignment_id(title: str) -> str:
    """Suggest a conservative shared identifier from an assignment title."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_title.strip())
    return suggestion.strip("_-").lower()


def normalize_writing_type(value: str) -> str:
    """Normalize teacher-friendly writing type input to lowercase snake case."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    writing_type = re.sub(r"[^a-z0-9]+", "_", ascii_value.strip().lower())
    writing_type = re.sub(r"_+", "_", writing_type).strip("_")
    if not writing_type:
        raise ValueError("writing type is required.")
    if re.fullmatch(r"[a-z][a-z0-9_]*", writing_type) is None:
        raise ValueError("writing type must start with a letter after normalization.")
    return writing_type


def parse_comma_separated_values(value: str) -> list[str]:
    """Return trimmed, nonblank values from comma-separated teacher input."""
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_optional_nonnegative_int(
    value: str,
    field_name: str,
) -> int | None:
    """Parse an optional nonnegative integer requirement."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a non-negative integer.") from error
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return parsed


def build_assignment_config(
    *,
    assignment_id: str,
    title: str,
    writing_type: str,
    student_prompt: str,
    standards_profile_id: str,
    focus_standard_ids: Sequence[str],
    review_unit: Mapping[str, Any],
    rating_scale: Mapping[str, Any],
    basic_requirements: Mapping[str, Any],
    minimum_requirement_policy: Mapping[str, Any],
    class_ids: Sequence[str] | None = None,
    class_id: str | None = None,
    created_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build and validate a v2 assignment config."""
    if class_ids is None:
        if class_id is None:
            raise ValueError("class_ids is required.")
        selected_class_ids = [class_id]
    elif class_id is not None:
        raise ValueError("Pass either class_ids or class_id, not both.")
    else:
        selected_class_ids = list(class_ids)

    if isinstance(created_at, datetime):
        timestamp = created_at.isoformat()
    elif created_at is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    else:
        timestamp = created_at

    assignment: dict[str, Any] = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": title,
        "class_ids": selected_class_ids,
        "writing_type": writing_type,
        "student_prompt": student_prompt,
        "standards_profile_id": standards_profile_id,
        "focus_standard_ids": list(focus_standard_ids),
        "review_unit": dict(review_unit),
        "rating_scale": dict(rating_scale),
        "basic_requirements": dict(basic_requirements),
        "minimum_requirement_policy": dict(minimum_requirement_policy),
        "created_at": timestamp,
        "updated_at": timestamp,
        "module_details": {},
    }
    validate_assignment_config(assignment)
    return assignment


def write_assignment_config(
    workspace_root: str | Path,
    class_id: str,
    assignment: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Write a validated assignment config to its canonical shared path."""
    return write_assignment_configs(
        workspace_root, (class_id,), assignment, overwrite=overwrite
    )[0]


@dataclass(frozen=True, slots=True)
class AssignmentBatchDestination:
    """Canonical preflight result for one assignment copy."""

    class_id: str
    path: Path
    exists: bool


def plan_assignment_config_destinations(
    workspace_root: str | Path,
    class_ids: Sequence[str],
    assignment: Mapping[str, Any],
) -> tuple[AssignmentBatchDestination, ...]:
    """Return validated canonical destinations without writing or creating paths."""
    assignment_data = dict(assignment)
    validate_assignment_config(assignment_data)
    selected = tuple(class_ids)
    if not selected or len(set(selected)) != len(selected):
        raise AssignmentConfigError("class_ids must be nonempty and unique.")
    root = canonical_workspace_root(workspace_root)
    assignment_id = str(assignment_data["assignment_id"])
    destinations: list[AssignmentBatchDestination] = []
    for class_id in selected:
        if class_id not in assignment_data["class_ids"]:
            raise AssignmentConfigError(
                "Assignment class_ids must include every selected class_id."
            )
        paths = quillan_work_paths(root, class_id, assignment_id)
        try:
            preflight_managed_work_layout(paths)
            preflight_work_file_destination(root, paths.work_ref, "assignment.json")
        except QuillanWorkPathError as error:
            raise AssignmentConfigError(str(error)) from error
        destinations.append(
            AssignmentBatchDestination(
                class_id=class_id,
                path=paths.assignment_path,
                exists=os.path.lexists(paths.assignment_path),
            )
        )
    return tuple(destinations)


def write_assignment_configs(
    workspace_root: str | Path,
    class_ids: Sequence[str],
    assignment: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    """Preflight all copies and conservatively compensate an incomplete batch."""
    assignment_data = dict(assignment)
    validate_assignment_config(assignment_data)
    selected = tuple(class_ids)
    if not selected or len(set(selected)) != len(selected):
        raise AssignmentConfigError("class_ids must be nonempty and unique.")
    for class_id in selected:
        if class_id not in assignment_data["class_ids"]:
            raise AssignmentConfigError(
                "Assignment class_ids must include every selected class_id."
            )
    root = canonical_workspace_root(workspace_root)
    assignment_id = str(assignment_data["assignment_id"])
    bundles = tuple(
        quillan_work_paths(root, class_id, assignment_id)
        for class_id in selected
    )
    originals: dict[Path, LoadedJsonRecord | None] = {}
    for paths in bundles:
        try:
            preflight_managed_work_layout(paths)
            preflight_work_file_destination(
                root, paths.work_ref, "assignment.json"
            )
        except QuillanWorkPathError as error:
            raise AssignmentConfigError(str(error)) from error
        path = paths.assignment_path
        if os.path.lexists(path):
            if not overwrite:
                raise FileExistsError(f"Assignment config already exists: {path}")
            originals[path] = load_quillan_assignment_context(
                root, paths.work_ref
            ).assignment_record
        else:
            originals[path] = None
    data = (
        json.dumps(assignment_data, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    journal = [
        _AssignmentWriteJournalEntry(
            paths.assignment_path,
            originals[paths.assignment_path],
            data,
        )
        for paths in bundles
    ]
    try:
        for paths in bundles:
            initialize_managed_work_layout(paths)
        for paths, entry in zip(bundles, journal, strict=True):
            path = paths.assignment_path

            def preflight(paths: Any = paths) -> None:
                preflight_managed_work_layout(paths)
                preflight_work_file_destination(
                    root, paths.work_ref, "assignment.json"
                )

            original = originals[path]
            if original is None:
                result = create_exclusive_record(
                    path,
                    data,
                    preflight=preflight,
                    verify_bytes=lambda loaded: _verify_assignment_bytes(
                        loaded, assignment_data
                    ),
                )
            else:
                result = revision_guarded_update(
                    path,
                    original.original_bytes,
                    data,
                    preflight=preflight,
                    verify_bytes=lambda loaded: _verify_assignment_bytes(
                        loaded, assignment_data
                    ),
                    lock_purpose="assignment-update",
                )
            entry.status = result.status
    except Exception as error:
        possible_paths: list[Path] = []
        diagnostics: list[str] = []
        if (
            isinstance(error, AtomicRecordDurabilityError)
            and error.possibly_durable_path is not None
        ):
            possible_paths.append(error.possibly_durable_path)
        if isinstance(error, AtomicRecordDurabilityError) and error.possible_lock_path:
            diagnostics.append(
                f"Possible stale record guard: {error.possible_lock_path}"
            )
        for paths, entry in reversed(tuple(zip(bundles, journal, strict=True))):
            if entry.status not in {"created", "updated"}:
                continue
            compensation_error, preserved = _compensate_assignment_entry(
                root,
                paths.work_ref,
                entry,
            )
            if compensation_error is not None:
                diagnostics.append(compensation_error)
                possible_paths.extend(preserved)
                error.add_note(compensation_error)
        possible = tuple(dict.fromkeys(possible_paths))
        suffix = ""
        if possible:
            suffix = " Possibly durable paths: " + "; ".join(map(str, possible))
        if diagnostics:
            suffix += " Rollback diagnostics: " + " | ".join(diagnostics)
        raise AssignmentBatchWriteError(
            f"Multi-class assignment write did not complete: {error}.{suffix}",
            possibly_durable_paths=possible,
            rollback_diagnostics=tuple(diagnostics),
        ) from error
    return tuple(paths.assignment_path for paths in bundles)


def _compensate_assignment_entry(
    root: Path,
    work_ref: Any,
    entry: _AssignmentWriteJournalEntry,
) -> tuple[str | None, tuple[Path, ...]]:
    """Undo only bytes still proven to belong to the current batch."""

    def preflight() -> None:
        preflight_work_file_destination(root, work_ref, "assignment.json")

    if entry.status == "updated":
        if entry.original is None:
            return (
                f"Updated assignment has no authoritative original snapshot: {entry.path}",
                (entry.path,),
            )
        original_bytes = entry.original.original_bytes
        try:
            revision_guarded_update(
                entry.path,
                entry.replacement_bytes,
                original_bytes,
                preflight=preflight,
                verify_bytes=lambda loaded: _verify_exact_bytes(
                    loaded, original_bytes
                ),
                lock_purpose="assignment-compensation",
            )
        except Exception as error:
            return (
                f"Could not conservatively restore updated assignment "
                f"{entry.path}: {error}",
                (entry.path,),
            )
        return None, ()

    if entry.status != "created":
        return None, ()
    displaced = entry.path.parent / (
        f".{entry.path.name}.assignment-compensation.{os.urandom(16).hex()}.displaced"
    )
    try:
        preflight()
        if os.path.lexists(displaced):
            raise OSError(f"compensation displacement already exists: {displaced}")
        os.replace(entry.path, displaced)
        actual = displaced.read_bytes()
        if actual == entry.replacement_bytes:
            displaced.unlink()
            return None, ()
        _restore_compensation_displacement(displaced, entry.path)
        preserved = tuple(
            path for path in (entry.path, displaced) if os.path.lexists(path)
        )
        return (
            f"Created assignment changed before compensation and was preserved: "
            f"{entry.path}",
            preserved or (entry.path,),
        )
    except Exception as error:
        if os.path.lexists(displaced):
            try:
                _restore_compensation_displacement(displaced, entry.path)
            except OSError as restore_error:
                error.add_note(f"Compensation restore also failed: {restore_error}")
        preserved = tuple(
            path for path in (entry.path, displaced) if os.path.lexists(path)
        )
        return (
            f"Could not conservatively remove created assignment {entry.path}: {error}",
            preserved or (entry.path,),
        )


def _restore_compensation_displacement(displaced: Path, target: Path) -> None:
    """Restore displaced concurrent bytes exclusively, never overwriting a writer."""
    if os.path.lexists(target):
        return
    try:
        os.link(displaced, target)
    except FileExistsError:
        return
    displaced.unlink()


def _verify_exact_bytes(actual: bytes, expected: bytes) -> None:
    if actual != expected:
        raise AssignmentConfigError("Compensated assignment bytes did not verify.")


def _verify_assignment_bytes(data: bytes, expected: dict[str, Any]) -> None:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AssignmentConfigError(f"Duplicate assignment JSON key: {key}")
            result[key] = value
        return result

    try:
        loaded = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                AssignmentConfigError(f"Invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AssignmentConfigError(
            f"Persisted assignment is not strict JSON: {error}"
        ) from error
    if not isinstance(loaded, dict):
        raise AssignmentConfigError("Persisted assignment is not an object.")
    validate_assignment_config(loaded)
    if loaded != expected:
        raise AssignmentConfigError(
            "Reloaded assignment differs from the committed model."
        )


def format_assignment_summary(
    assignment: Mapping[str, Any],
    assignment_path: str | Path,
    workspace_root: str | Path | None = None,
) -> str:
    """Return a concise human-readable assignment summary."""
    path = Path(assignment_path)
    if path.is_absolute():
        if workspace_root is None:
            raise ValueError(
                "An absolute assignment path requires the exact workspace root."
            )
        try:
            path = path.relative_to(Path(workspace_root))
        except ValueError as error:
            raise ValueError(
                "Assignment path is outside the exact workspace root."
            ) from error
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Assignment path is not canonical workspace-relative text.")
    path_text = path.as_posix()
    class_ids = ", ".join(str(value) for value in assignment["class_ids"])
    focus_standard_ids = [str(value) for value in assignment["focus_standard_ids"]]
    focus_text = ", ".join(focus_standard_ids)
    review_unit = assignment.get("review_unit", {})
    rating_scale = assignment.get("rating_scale", {})
    lines = [
        f"Assignment path: {path_text}",
        f"Schema version: {assignment['schema_version']}",
        f"Assignment ID: {assignment['assignment_id']}",
        f"Title: {assignment['title']}",
        f"Class IDs: {class_ids}",
        f"Writing type: {assignment['writing_type']}",
        f"Student prompt: {assignment['student_prompt']}",
        f"Standards profile ID: {assignment['standards_profile_id']}",
        f"Focus standard IDs ({len(focus_standard_ids)}): {focus_text}",
    ]
    if isinstance(review_unit, Mapping):
        lines.append(
            "Review unit: "
            f"{review_unit.get('type')} "
            f"({review_unit.get('singular_label')}/"
            f"{review_unit.get('plural_label')})"
        )
    if isinstance(rating_scale, Mapping):
        levels = rating_scale.get("levels")
        if isinstance(levels, Sequence) and not isinstance(levels, (str, bytes)):
            lines.append(
                f"Rating scale: {rating_scale.get('scale_id')} "
                f"({len(levels)} levels)"
            )
            for level in levels:
                if isinstance(level, Mapping):
                    lines.append(
                        "  "
                        f"{level.get('value')}: {level.get('label')} - "
                        f"{level.get('description')}"
                    )
    lines.append(f"Basic requirements: {dict(assignment['basic_requirements'])}")
    policy = assignment["minimum_requirement_policy"]
    lines.append(f"Minimum requirement policy: {dict(policy)}")
    return "\n".join(lines)


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _available_class_folders(workspace_root: Path) -> tuple[ClassFolder, ...]:
    return list_class_folders(workspace_root, require_roster=True)


def _prompt_class_folder(workspace_root: Path) -> ClassFolder | None:
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    folders = _available_class_folders(workspace_root)
    if not folders:
        print("No class rosters found. Create a class roster first.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print_navigation_options()
    print()
    selection = input("Select class for assignment: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(folders):
        return folders[int(selection) - 1]
    for folder in folders:
        if folder.class_id == selection:
            return folder
    print(f"Error: Class not found: {selection}")
    return None


def _parse_class_folder_selection(
    selection: str,
    folders: Sequence[ClassFolder],
) -> tuple[ClassFolder, ...]:
    """Parse comma-separated class numbers and class IDs in teacher-entered order."""
    selected_folders: list[ClassFolder] = []
    seen_class_ids: set[str] = set()
    tokens = parse_comma_separated_values(selection)
    if not tokens:
        raise ValueError("At least one class selection is required.")

    by_class_id = {folder.class_id: folder for folder in folders}
    for token in tokens:
        if token.isdigit():
            index = int(token)
            if not 1 <= index <= len(folders):
                raise ValueError(f"Class selection not found: {token}")
            folder = folders[index - 1]
        else:
            if token not in by_class_id:
                raise ValueError(f"Class not found: {token}")
            folder = by_class_id[token]
        if folder.class_id in seen_class_ids:
            raise ValueError(f"Duplicate class selection: {token}")
        seen_class_ids.add(folder.class_id)
        selected_folders.append(folder)
    return tuple(selected_folders)


def _prompt_assignment_class_folders(workspace_root: Path) -> tuple[ClassFolder, ...] | None:
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    folders = _available_class_folders(workspace_root)
    if not folders:
        print("No class rosters found. Create a class roster first.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print()
    print("Select class(es) for assignment.")
    print(
        "Enter one number, multiple numbers separated by commas, "
        "or exact class_id values."
    )
    print()
    print("Examples:")
    print("  1")
    print("  1,3")
    print("  english10_p2,english10_p4")
    print()
    print_navigation_options()
    print()
    selection = input("Select class(es) for assignment: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return None
    try:
        return _parse_class_folder_selection(selection, folders)
    except ValueError as error:
        print(f"Error: {error}")
        return None


def _print_assignment_section_header(
    title: str,
    *,
    class_id: str | None = None,
    class_ids: Sequence[str] | None = None,
    assignment_id: str | None = None,
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)
    if class_ids is not None:
        class_label = ", ".join(class_ids)
        label = "Class" if len(class_ids) == 1 else "Classes"
        print(f"{label}: {class_label}")
    if class_id is not None:
        print(f"Class: {class_id}")
    if assignment_id is not None:
        print(f"Assignment ID: {assignment_id}")
    if class_ids is not None or class_id is not None or assignment_id is not None:
        print()


def _required_input(prompt: str, field_name: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError(f"{field_name} is required.")
    return value


def _prompt_basic_requirements() -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    print(
        "Basic requirements (leave blank to omit). These are teacher-entered "
        "requirements, not automatic analysis."
    )
    for field_name in _NUMERIC_REQUIREMENTS:
        parsed = parse_optional_nonnegative_int(
            input(f"  {field_name}: "),
            field_name,
        )
        if parsed is not None:
            requirements[field_name] = parsed
    required_elements = parse_comma_separated_values(
        input("  required_elements, comma-separated: ")
    )
    if required_elements:
        requirements["required_elements"] = required_elements
    return requirements


def _prompt_numbered_selection(
    items: Sequence[_T],
    *,
    prompt: str,
    label: str,
) -> _T | None:
    selection = input(prompt).strip()
    if selection.isdigit() and 1 <= int(selection) <= len(items):
        return items[int(selection) - 1]
    print(f"Error: {label} not found: {selection}")
    return None


def _prompt_standards_selection(
    workspace_root: Path,
) -> tuple[str, list[str]] | None:
    try:
        library = load_standards_for_selection(workspace_root)
    except (OSError, StandardsReadError, StandardsValidationError) as error:
        print(f"Error: could not load pds-core standards library: {error}")
        return None

    profiles = list_profiles_for_selection(library)
    if not profiles:
        print(
            "No pds-core standards profiles found. Create or import standards "
            "through pds-core first."
        )
        return None

    print("Available standards profiles:")
    for index, profile in enumerate(profiles, start=1):
        print(f"{index}. {profile.label}")
    print()
    selected_profile = _prompt_numbered_selection(
        profiles,
        prompt="Select standards profile: ",
        label="standards profile",
    )
    if selected_profile is None:
        return None

    try:
        standards = list_standards_for_profile_selection(
            library,
            selected_profile.profile_id,
        )
    except StandardsValidationError as error:
        print(f"Error: could not list profile standards: {error}")
        return None
    if not standards:
        print(
            "Selected pds-core standards profile has no standards available "
            "for Quillan."
        )
        return None

    _print_assignment_section_header("Focus Standard Selection")
    print(f"Standards profile: {selected_profile.label}")
    print()
    print("Available standards:")
    for index, standard in enumerate(standards, start=1):
        print(f"{index}. {standard.label}")
    print()
    selected_standards = _prompt_focus_standards(standards)
    if selected_standards is None:
        return None
    return selected_profile.profile_id, selected_standards


def _confirm_standards_profile_prerequisite(workspace_root: Path) -> bool:
    from quillan.menu_navigation import (
        NavigationChoice,
        navigation_hint,
        parse_navigation_choice,
        print_navigation_options,
    )

    _print_assignment_section_header("Create Writing Assignment")
    print("Assignment creation requires an existing PDS Core standards profile.")
    print()

    try:
        library = load_standards_for_selection(workspace_root)
    except (OSError, StandardsReadError, StandardsValidationError) as error:
        print(
            "Quillan could not load the PDS Core standards library for this "
            "workspace."
        )
        print()
        print(
            "Create or repair standards/profile data in PDS Core, then return "
            "to Quillan."
        )
        print()
        print(f"Error: {error}")
        print()
        print_navigation_options()
        print()
        selection = input("Select an option: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            return False
        print(f"Invalid selection. {navigation_hint()}")
        return False

    profiles = list_profiles_for_selection(library)
    if not profiles:
        print("No standards profiles were found in this workspace.")
        print()
        print(
            "Create or import standards and standards profiles in PDS Core, "
            "then return to Quillan to create the assignment."
        )
        print()
        print_navigation_options()
        print()
        selection = input("Select an option: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            return False
        print(f"Invalid selection. {navigation_hint()}")
        return False

    print(
        "Quillan uses a standards profile to let you choose Focus Standards "
        "for this assignment. Standards and standards profiles are created in "
        "PDS Core, not in Quillan."
    )
    print()
    print(f"Standards profiles found: {len(profiles)}")
    print()
    print("1. Continue")
    print_navigation_options()
    print()
    selection = input("Select an option: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "1":
        return True
    if selection == "" or navigation is NavigationChoice.BACK:
        return False
    print(f"Invalid selection. {navigation_hint()}")
    return False


def _prompt_focus_standards(
    standards: Sequence[StandardSelectionItem],
) -> list[str] | None:
    selection = input("Select Focus Standards by number, comma-separated: ").strip()
    if not selection:
        print("Error: at least one Focus Standard is required.")
        return None
    selected_ids: list[str] = []
    seen: set[str] = set()
    for item in parse_comma_separated_values(selection):
        if not item.isdigit() or not 1 <= int(item) <= len(standards):
            print(f"Error: focus standard selection not found: {item}")
            return None
        standard_id = standards[int(item) - 1].standard_id
        if standard_id in seen:
            print(f"Error: duplicate focus standard selection: {item}")
            return None
        seen.add(standard_id)
        selected_ids.append(standard_id)
    return selected_ids


def prompt_create_assignment() -> int:
    """Prompt for and write one validated writing assignment config."""
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    if not _confirm_standards_profile_prerequisite(workspace_root):
        return 1
    _print_assignment_section_header("Select Assignment Classes")
    class_folders = _prompt_assignment_class_folders(workspace_root)
    if class_folders is None:
        return 1
    class_ids = [folder.class_id for folder in class_folders]

    try:
        _print_assignment_section_header(
            "Assignment Identity",
            class_ids=class_ids,
        )
        title = _required_input("Assignment title: ", "assignment title")
        suggested_id = suggest_assignment_id(title)
        if not suggested_id:
            raise ValueError("assignment_id could not be suggested from title.")
        print(f"Suggested assignment ID: {suggested_id}")
        assignment_id = input("Assignment ID [press Enter to accept]: ").strip()
        if not assignment_id:
            assignment_id = suggested_id
        validate_identifier(assignment_id, "assignment_id")

        _print_assignment_section_header(
            "Writing Prompt",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        writing_type = _prompt_writing_type()
        student_prompt = _prompt_student_prompt()
        _print_assignment_section_header(
            "Standards Profile",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        standards_selection = _prompt_standards_selection(workspace_root)
        if standards_selection is None:
            return 1
        standards_profile_id, focus_standard_ids = standards_selection
        _print_assignment_section_header(
            "Review Unit Setup",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        review_unit = _prompt_review_unit()
        _print_assignment_section_header(
            "Rating Scale Setup",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        rating_scale = _prompt_rating_scale()
        _print_assignment_section_header(
            "Basic Requirements",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        basic_requirements = _prompt_basic_requirements()
        _print_assignment_section_header(
            "Minimum Requirement Policy",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        minimum_requirement_policy = _prompt_minimum_requirement_policy()

        assignment = build_assignment_config(
            assignment_id=assignment_id,
            title=title,
            class_ids=class_ids,
            writing_type=writing_type,
            student_prompt=student_prompt,
            standards_profile_id=standards_profile_id,
            focus_standard_ids=focus_standard_ids,
            review_unit=review_unit,
            rating_scale=rating_scale,
            basic_requirements=basic_requirements,
            minimum_requirement_policy=minimum_requirement_policy,
        )
    except (AssignmentConfigError, IdentifierValidationError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    try:
        destinations = plan_assignment_config_destinations(
            workspace_root, class_ids, assignment
        )
    except AssignmentConfigError as error:
        print(f"Error: {error}")
        return 1
    output_paths = [destination.path for destination in destinations]
    _print_assignment_section_header(
        "Review Assignment Before Saving",
        class_ids=class_ids,
        assignment_id=assignment_id,
    )
    print(format_assignment_summary(assignment, output_paths[0], workspace_root))
    print()
    class_count = len(class_ids)
    class_word = "class" if class_count == 1 else "classes"
    print(f"This assignment will be saved for {class_count} {class_word}:")
    for class_id, output_path in zip(class_ids, output_paths, strict=True):
        print(f"- {class_id}: {output_path.relative_to(workspace_root).as_posix()}")
    if not _prompt_yes_no("Save this assignment? [Y/n]: ", default=True):
        print("Canceled: assignment was not saved.")
        return 0

    overwrite = False
    existing_paths = [
        (destination.class_id, destination.path)
        for destination in destinations
        if destination.exists
    ]
    if existing_paths:
        _print_assignment_section_header(
            "Confirm Assignment Overwrite",
            class_ids=class_ids,
            assignment_id=assignment_id,
        )
        print("Assignment config already exists in one or more selected classes:")
        print()
        for class_id, output_path in existing_paths:
            print(
                f"- {class_id}: "
                f"{output_path.relative_to(workspace_root).as_posix()}"
            )
        print()
        confirmation = input(
            "Type OVERWRITE to replace existing assignment configs: "
        ).strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing assignments were not changed.")
            return 1
        overwrite = True

    try:
        saved_paths = list(
            write_assignment_configs(
                workspace_root,
                class_ids,
                assignment,
                overwrite=overwrite,
            )
        )
    except (AssignmentConfigError, OSError, FileExistsError) as error:
        print(f"Error: {error}")
        return 1
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Assignment Saved")
    if len(saved_paths) == 1:
        print(
            "Saved assignment: "
            f"{saved_paths[0].relative_to(workspace_root).as_posix()}"
        )
    else:
        print(f"Saved assignment for {len(saved_paths)} classes:")
        for class_id, saved_path in zip(class_ids, saved_paths, strict=True):
            print(
                f"- {class_id}: "
                f"{saved_path.relative_to(workspace_root).as_posix()}"
            )
    return 0


def _prompt_yes_no(prompt: str, *, default: bool) -> bool:
    response = input(prompt).strip().lower()
    if not response:
        return default
    return response in {"y", "yes"}


def _prompt_student_prompt() -> str:
    return _required_input(
        "Student-facing assignment prompt: ",
        "student-facing assignment prompt",
    )


def _prompt_writing_type() -> str:
    print("Writing type:")
    print("Examples: literary_analysis, argument, research_paper, reflection")
    print("You may type spaces; Quillan will store lowercase snake_case.")
    print()
    raw = _required_input("Writing type: ", "writing type")
    normalized = normalize_writing_type(raw)
    if normalized != raw.strip():
        print(f"Stored writing type: {normalized}")
    return normalized


def default_review_unit() -> dict[str, str]:
    """Return a fresh copy of the menu's default review-unit config."""
    return dict(_DEFAULT_REVIEW_UNIT)


def _prompt_review_unit() -> dict[str, str]:
    print(
        "Review units are the chunks of student writing the teacher may review "
        "later."
    )
    if _prompt_yes_no("Use default paragraph review units? [Y/n]: ", default=True):
        return default_review_unit()
    return {
        "type": _required_input("Review-unit type: ", "review-unit type"),
        "singular_label": _required_input(
            "Review-unit singular label: ",
            "review-unit singular label",
        ),
        "plural_label": _required_input(
            "Review-unit plural label: ",
            "review-unit plural label",
        ),
    }


def default_rating_scale() -> dict[str, Any]:
    """Return a fresh copy of the menu's four-level standards scale."""
    levels = _DEFAULT_RATING_SCALE["levels"]
    assert isinstance(levels, list)
    return {
        "scale_id": _DEFAULT_RATING_SCALE["scale_id"],
        "levels": [dict(level) for level in levels],
    }


def _prompt_rating_scale() -> dict[str, Any]:
    print("Rating scale for standards-based review:")
    if _prompt_yes_no("Use default four-level standards scale? [Y/n]: ", default=True):
        return default_rating_scale()

    scale_id = _required_input("Rating scale ID: ", "rating scale ID")
    level_count = parse_optional_nonnegative_int(
        input("Number of rating levels: "),
        "number of rating levels",
    )
    if level_count is None or level_count <= 0:
        raise ValueError("number of rating levels must be a positive integer.")

    levels: list[dict[str, Any]] = []
    for index in range(1, level_count + 1):
        print(f"Rating level {index}:")
        value = parse_optional_nonnegative_int(
            input("  value: "),
            "rating level value",
        )
        if value is None:
            raise ValueError("rating level value is required.")
        levels.append(
            {
                "value": value,
                "label": _required_input("  label: ", "rating level label"),
                "description": _required_input(
                    "  description: ",
                    "rating level description",
                ),
            }
        )
    return {"scale_id": scale_id, "levels": levels}


def _prompt_minimum_requirement_policy() -> dict[str, bool]:
    allow_return = _prompt_yes_no(
        "Allow teacher to return work without full standards review if minimum "
        "requirements are unmet? [Y/n]: ",
        default=True,
    )
    return {"allow_return_without_full_review": allow_return}


def _normalize_path_input(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
        return stripped[1:-1]
    return stripped


def prompt_view_validate_assignment() -> int:
    """Select, load, validate, and summarize a canonical assignment config."""
    from quillan.assignment_setup import load_canonical_assignment
    from quillan.menu import clear_screen, print_menu_header

    print_menu_header("View/Validate Assignment")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    choice = prompt_assignment_choice(workspace_root)
    if choice is None:
        return 0
    try:
        plan = load_canonical_assignment(
            workspace_root, choice.class_id, choice.assignment_id
        )
    except (AssignmentConfigError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    clear_screen()
    print_menu_header("Assignment Validation Result")
    print("Assignment config is valid.")
    print(format_assignment_summary(plan.assignment, plan.path, workspace_root))
    return 0


def launch_assignment_menu() -> int:
    """Launch the teacher-facing assignment management submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import (
        NavigationChoice,
        navigation_hint,
        parse_navigation_choice,
        print_navigation_options,
    )

    try:
        while True:
            clear_screen()
            print_menu_header("Assignment Management")
            print("1. Create writing assignment")
            print("2. View/validate assignment")
            print("3. Printable Response Pages")
            print_navigation_options()
            print()
            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(choice)
            print()

            if navigation is NavigationChoice.BACK:
                return 0
            workflows = {
                "1": prompt_create_assignment,
                "2": prompt_view_validate_assignment,
            }
            workflow = workflows.get(choice)
            if choice == "3":
                from quillan.printable_response_workflows import (
                    launch_printable_response_menu,
                )

                launch_printable_response_menu()
            elif workflow is None:
                print(f"Invalid selection. {navigation_hint()}")
            else:
                clear_screen()
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting assignment menu.")
        return 0

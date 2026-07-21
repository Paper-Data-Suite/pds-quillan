"""Pure canonical paths and safe layout initialization for Quillan work."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from pds_core.identifiers import validate_identifier
from pds_core.routes import (
    class_roster_path,
    module_work_collection_dir,
    module_work_dir,
    safe_module_work_descendant,
)
from pds_core.routing_models import ModuleWorkRef

from quillan.pds_contract import QUILLAN_MODULE_ID


class QuillanWorkPathError(ValueError):
    """Raised when a Quillan work path cannot be used safely."""


@dataclass(frozen=True, slots=True)
class QuillanWorkPaths:
    """Canonical paths for one module-qualified Quillan assignment."""

    work_ref: ModuleWorkRef
    roster_path: Path
    work_collection_dir: Path
    work_root: Path
    assignment_path: Path
    response_pages_dir: Path
    response_page_issuances_dir: Path
    response_page_records_dir: Path
    templates_dir: Path
    scans_dir: Path
    response_page_observations_dir: Path
    routed_evidence_root: Path
    submissions_dir: Path
    exports_dir: Path


def quillan_work_ref(class_id: str, assignment_id: str) -> ModuleWorkRef:
    """Return the complete Core work identity for a Quillan assignment."""
    return ModuleWorkRef(
        module_id=QUILLAN_MODULE_ID,
        class_id=class_id,
        work_id=assignment_id,
    )


def quillan_work_collection_dir(
    workspace_root: str | Path,
    class_id: str,
) -> Path:
    """Return Quillan's work collection for one class without creating it."""
    return module_work_collection_dir(
        workspace_root,
        class_id,
        QUILLAN_MODULE_ID,
    )


def quillan_work_paths(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> QuillanWorkPaths:
    """Return every standard path for one Quillan assignment without I/O."""
    work_ref = quillan_work_ref(class_id, assignment_id)
    return QuillanWorkPaths(
        work_ref=work_ref,
        roster_path=class_roster_path(workspace_root, class_id),
        work_collection_dir=module_work_collection_dir(
            workspace_root,
            class_id,
            QUILLAN_MODULE_ID,
        ),
        work_root=module_work_dir(workspace_root, work_ref),
        assignment_path=safe_module_work_descendant(
            workspace_root, work_ref, "assignment.json"
        ),
        response_pages_dir=safe_module_work_descendant(
            workspace_root, work_ref, "response_pages"
        ),
        response_page_issuances_dir=safe_module_work_descendant(
            workspace_root, work_ref, Path("response_pages") / "issuances"
        ),
        response_page_records_dir=safe_module_work_descendant(
            workspace_root, work_ref, Path("response_pages") / "pages"
        ),
        templates_dir=safe_module_work_descendant(
            workspace_root, work_ref, "templates"
        ),
        scans_dir=safe_module_work_descendant(workspace_root, work_ref, "scans"),
        response_page_observations_dir=safe_module_work_descendant(
            workspace_root, work_ref, Path("scans") / "observations"
        ),
        routed_evidence_root=safe_module_work_descendant(
            workspace_root, work_ref, Path("scans") / "evidence"
        ),
        submissions_dir=safe_module_work_descendant(
            workspace_root, work_ref, "submissions"
        ),
        exports_dir=safe_module_work_descendant(
            workspace_root, work_ref, "exports"
        ),
    )


def student_submission_dir(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
) -> Path:
    """Return one validated student's Quillan submission directory."""
    validated_work = _require_quillan_work_ref(work_ref)
    validated_student_id = validate_identifier(student_id, "student_id")
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("submissions") / validated_student_id,
    )


def response_page_issuance_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance_id: str,
) -> Path:
    """Return one exact immutable issuance path without filesystem access."""
    from quillan.printable_response_records import validate_issuance_id

    validated_work = _require_quillan_work_ref(work_ref)
    validated_id = validate_issuance_id(issuance_id)
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("response_pages") / "issuances" / f"{validated_id}.json",
    )


def response_page_record_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    page_id: str,
) -> Path:
    """Return one exact immutable response-page path without filesystem access."""
    from quillan.printable_response_records import validate_page_id

    validated_work = _require_quillan_work_ref(work_ref)
    validated_id = validate_page_id(page_id)
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("response_pages") / "pages" / f"{validated_id}.json",
    )


def response_page_observations_dir(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> Path:
    """Return the canonical immutable observation collection."""
    validated_work = _require_quillan_work_ref(work_ref)
    return safe_module_work_descendant(
        workspace_root, validated_work, Path("scans") / "observations"
    )


def response_page_observation_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    observation_id: str,
) -> Path:
    """Return one canonical immutable response-page observation path."""
    from quillan.response_page_observations import validate_observation_id

    validated_work = _require_quillan_work_ref(work_ref)
    validated_id = validate_observation_id(observation_id)
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("scans") / "observations" / f"{validated_id}.json",
    )


def routed_evidence_root(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> Path:
    """Return the canonical routed-evidence collection."""
    validated_work = _require_quillan_work_ref(work_ref)
    return safe_module_work_descendant(
        workspace_root, validated_work, Path("scans") / "evidence"
    )


def routed_evidence_issuance_dir(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance_id: str,
) -> Path:
    """Return one issuance's canonical routed-evidence directory."""
    from quillan.printable_response_records import validate_issuance_id

    validated_work = _require_quillan_work_ref(work_ref)
    validated_issuance = validate_issuance_id(issuance_id)
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("scans") / "evidence" / validated_issuance,
    )


def routed_evidence_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    issuance_id: str,
    student_id: str,
    logical_page: int,
    observation_id: str,
    extension: str,
) -> Path:
    """Return a readable but non-authoritative routed-evidence path."""
    from quillan.response_page_observations import validate_observation_id

    validated_work = _require_quillan_work_ref(work_ref)
    validated_student = validate_identifier(student_id, "student_id")
    validated_observation = validate_observation_id(observation_id)
    issuance_dir = routed_evidence_issuance_dir(
        workspace_root, validated_work, issuance_id
    )
    if isinstance(logical_page, bool) or not isinstance(logical_page, int) or logical_page < 1:
        raise QuillanWorkPathError("logical_page must be a positive integer.")
    if not isinstance(extension, str):
        raise QuillanWorkPathError("extension must be a string.")
    normalized_extension = extension.lower()
    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"
    if normalized_extension not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise QuillanWorkPathError("Unsupported routed-evidence extension.")
    filename = (
        f"response_{validated_student}_pg_{logical_page:03d}__"
        f"{validated_observation}{normalized_extension}"
    )
    return issuance_dir / filename


def submission_manifest_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
) -> Path:
    """Return one validated student's canonical submission manifest path."""
    validated_work = _require_quillan_work_ref(work_ref)
    validated_student_id = validate_identifier(student_id, "student_id")
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("submissions") / validated_student_id / "submission.json",
    )


def review_record_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
) -> Path:
    """Return one validated student's canonical review record path."""
    validated_work = _require_quillan_work_ref(work_ref)
    validated_student_id = validate_identifier(student_id, "student_id")
    return safe_module_work_descendant(
        workspace_root,
        validated_work,
        Path("submissions") / validated_student_id / "review.json",
    )


def relative_assignment_path(class_id: str, assignment_id: str) -> str:
    """Return the canonical workspace-relative assignment record path."""
    return quillan_work_paths(Path(), class_id, assignment_id).assignment_path.as_posix()


def relative_submission_manifest_path(
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> str:
    """Return the canonical workspace-relative submission manifest path."""
    work_ref = quillan_work_ref(class_id, assignment_id)
    return submission_manifest_path(Path(), work_ref, student_id).as_posix()


def preflight_managed_work_layout(paths: QuillanWorkPaths) -> QuillanWorkPaths:
    """Validate the complete static work layout without filesystem mutation."""
    workspace_root = _workspace_root_for(paths)
    _preflight_directories(workspace_root, _managed_directories(paths))
    return paths


def preflight_quillan_work_collection(
    workspace_root: str | Path,
    class_id: str,
) -> Path:
    """Validate Quillan's work collection chain without filesystem mutation."""
    root = Path(workspace_root)
    collection = quillan_work_collection_dir(root, class_id)
    _preflight_path_chain(root, collection, expect_file=False)
    return collection


def preflight_work_file_destination(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    relative_path: str | Path,
) -> Path:
    """Validate a contained Quillan work file destination without mutation."""
    validated_work = _require_quillan_work_ref(work_ref)
    target = safe_module_work_descendant(
        workspace_root, validated_work, relative_path
    )
    _preflight_file_destination(Path(workspace_root), target)
    return target


def preflight_work_directory_destination(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    relative_path: str | Path,
) -> Path:
    """Validate a contained Quillan work directory without mutation."""
    validated_work = _require_quillan_work_ref(work_ref)
    target = safe_module_work_descendant(
        workspace_root, validated_work, relative_path
    )
    _preflight_path_chain(Path(workspace_root), target, expect_file=False)
    return target


def initialize_managed_work_layout(paths: QuillanWorkPaths) -> QuillanWorkPaths:
    """Preflight and create only Quillan's static managed work directories."""
    preflight_managed_work_layout(paths)
    for directory in _managed_directories(paths):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def initialize_student_submission_dir(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
) -> Path:
    """Safely create only the requested student's submission directory."""
    validated_work = _require_quillan_work_ref(work_ref)
    target = student_submission_dir(workspace_root, validated_work, student_id)
    submissions = safe_module_work_descendant(
        workspace_root, validated_work, "submissions"
    )
    root = Path(workspace_root)
    _preflight_directories(root, (submissions, target))
    target.mkdir(parents=True, exist_ok=True)
    return target


def _preflight_arbitrary_file_destination(path: str | Path) -> Path:
    """Validate a low-level path writer destination without creating anything."""
    target = _absolute(Path(path))
    _preflight_file_destination(Path(target.anchor), target)
    return Path(path)


def _require_quillan_work_ref(work_ref: ModuleWorkRef) -> ModuleWorkRef:
    if not isinstance(work_ref, ModuleWorkRef):
        raise QuillanWorkPathError("work_ref must be a ModuleWorkRef.")
    # Core revalidates all fields when constructing a canonical work path.
    module_work_dir(Path(), work_ref)
    if work_ref.module_id != QUILLAN_MODULE_ID:
        raise QuillanWorkPathError(
            f"work_ref.module_id must be {QUILLAN_MODULE_ID!r}."
        )
    return work_ref


def _workspace_root_for(paths: QuillanWorkPaths) -> Path:
    if not isinstance(paths, QuillanWorkPaths):
        raise QuillanWorkPathError("paths must be a QuillanWorkPaths instance.")
    try:
        workspace_root = paths.roster_path.parents[2]
    except IndexError as error:
        raise QuillanWorkPathError("Path bundle does not contain a workspace root.") from error
    expected = quillan_work_paths(
        workspace_root,
        paths.work_ref.class_id,
        paths.work_ref.work_id,
    )
    if paths != expected:
        raise QuillanWorkPathError("Path bundle is not internally canonical.")
    return workspace_root


def _managed_directories(paths: QuillanWorkPaths) -> tuple[Path, ...]:
    return (
        paths.work_root,
        paths.response_pages_dir,
        paths.response_page_issuances_dir,
        paths.response_page_records_dir,
        paths.templates_dir,
        paths.scans_dir,
        paths.submissions_dir,
        paths.exports_dir,
    )


def _preflight_directories(
    workspace_root: Path,
    directories: tuple[Path, ...],
) -> None:
    absolute_root = _absolute(workspace_root)
    _preflight_path_chain(absolute_root, absolute_root, expect_file=False)
    for directory in directories:
        absolute_directory = _absolute(directory)
        try:
            absolute_directory.relative_to(absolute_root)
        except ValueError as error:
            raise QuillanWorkPathError(
                f"Managed directory escapes workspace root: {directory}"
            ) from error
        _preflight_path_chain(absolute_root, absolute_directory, expect_file=False)


def _preflight_file_destination(root: Path, target: Path) -> None:
    _preflight_path_chain(root, target, expect_file=True)


def _preflight_path_chain(
    root: Path,
    target: Path,
    *,
    expect_file: bool,
) -> None:
    absolute_root = _absolute(root)
    absolute_target = _absolute(target)
    try:
        relative = absolute_target.relative_to(absolute_root)
    except ValueError as error:
        raise QuillanWorkPathError(
            f"Managed path escapes preflight root: {target}"
        ) from error
    candidates = [absolute_root]
    current = absolute_root
    for component in relative.parts:
        current /= component
        candidates.append(current)
    for index, candidate in enumerate(candidates):
        if not _lexists(candidate):
            continue
        if _is_link_like(candidate):
            raise QuillanWorkPathError(
                f"Managed path must not be a symlink or junction: {candidate}"
            )
        is_target = index == len(candidates) - 1
        if is_target and expect_file:
            if not candidate.is_file():
                raise QuillanWorkPathError(
                    f"Managed file path is not a regular file: {candidate}"
                )
        elif not candidate.is_dir():
            raise QuillanWorkPathError(
                f"Managed directory path is not a directory: {candidate}"
            )


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


__all__ = [
    "QuillanWorkPathError",
    "QuillanWorkPaths",
    "initialize_managed_work_layout",
    "initialize_student_submission_dir",
    "preflight_managed_work_layout",
    "preflight_quillan_work_collection",
    "preflight_work_file_destination",
    "preflight_work_directory_destination",
    "quillan_work_collection_dir",
    "quillan_work_paths",
    "quillan_work_ref",
    "relative_assignment_path",
    "relative_submission_manifest_path",
    "response_page_observation_path",
    "response_page_observations_dir",
    "response_page_issuance_path",
    "response_page_record_path",
    "routed_evidence_issuance_dir",
    "routed_evidence_path",
    "routed_evidence_root",
    "review_record_path",
    "student_submission_dir",
    "submission_manifest_path",
]

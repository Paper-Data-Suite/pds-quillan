"""Canonical assignment, submission, and review record service contexts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeAlias, cast

from pds_core.identifiers import validate_identifier
from pds_core.routing_models import ModuleWorkRef

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.assignments import AssignmentConfigError, validate_assignment_config
from quillan.review_record import ReviewRecordError, validate_review_record
from quillan.submission_manifest import (
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _preflight_arbitrary_file_destination,
    feedback_markdown_path,
    feedback_pdf_path,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
    review_record_path,
    student_exports_dir,
    student_submission_dir,
    submission_manifest_path,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


class QuillanRecordContextError(ValueError):
    """Base error for canonical Quillan record-context operations."""


class UnsafeRecordPathError(QuillanRecordContextError):
    """A canonical path chain is unsafe, linked, escaped, or the wrong type."""


class MissingAssignmentError(QuillanRecordContextError):
    """The canonical module-qualified assignment record is missing."""


class InvalidAssignmentError(QuillanRecordContextError):
    """The canonical assignment record is invalid."""


class MissingSubmissionError(QuillanRecordContextError):
    """The canonical submission manifest is missing."""


class InvalidSubmissionError(QuillanRecordContextError):
    """The canonical submission manifest is invalid."""


class MissingReviewError(QuillanRecordContextError):
    """A required canonical review record is missing."""


class InvalidReviewError(QuillanRecordContextError):
    """The canonical review record is invalid."""

    def __init__(
        self,
        message: str,
        *,
        submission_record: LoadedJsonRecord | None = None,
    ) -> None:
        super().__init__(message)
        self.submission_record = submission_record


class OrphanReviewError(QuillanRecordContextError):
    """A review exists without its canonical submission manifest."""


class RecordIdentityMismatchError(QuillanRecordContextError):
    """A loaded record does not match the requested work identity."""


class ReviewAlreadyExistsError(QuillanRecordContextError):
    """A review exists when the operation requires it to be absent."""


class ReviewLoadingPolicy(str, Enum):
    """Explicit review-presence policy for student-context loading."""

    REVIEW_REQUIRED = "review_required"
    REVIEW_OPTIONAL = "review_optional"
    REVIEW_MUST_BE_ABSENT = "review_must_be_absent"


@dataclass(frozen=True, slots=True)
class LoadedJsonRecord:
    """One validated JSON model inseparably bound to its source bytes."""

    path: Path
    relative_path: str
    original_bytes: bytes
    value: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if type(self.path) is not type(Path()) or not self.path.is_absolute():
            raise QuillanRecordContextError("Loaded record path must be an absolute Path.")
        if type(self.relative_path) is not str or not self.relative_path:
            raise QuillanRecordContextError(
                "Loaded record relative_path must be non-empty POSIX text."
            )
        relative = Path(self.relative_path)
        if (
            relative.is_absolute()
            or "\\" in self.relative_path
            or self.relative_path != relative.as_posix()
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise QuillanRecordContextError(
                "Loaded record relative_path must be canonical workspace-relative POSIX text."
            )
        if type(self.original_bytes) is not bytes:
            raise QuillanRecordContextError("Loaded record original_bytes must be exact bytes.")
        if type(self.value) is not type(MappingProxyType({})):
            raise QuillanRecordContextError(
                "Loaded record value must be a recursively immutable mapping."
            )
        if not _is_recursively_frozen(self.value):
            raise QuillanRecordContextError(
                "Loaded record value contains mutable or non-JSON data."
            )
        parsed = _strict_json_object(self.original_bytes, self.path)
        if _freeze_mapping(parsed) != self.value:
            raise QuillanRecordContextError(
                "Loaded record value does not agree with original_bytes."
            )


@dataclass(frozen=True, slots=True)
class QuillanAssignmentRecordPaths:
    """Exact canonical record paths for one Quillan assignment."""

    workspace_root: Path
    work_ref: ModuleWorkRef
    work_root: Path
    assignment_path: Path
    submissions_dir: Path
    scans_dir: Path
    exports_dir: Path

    def __post_init__(self) -> None:
        _require_absolute_workspace_root(self.workspace_root)
        expected = quillan_work_paths(
            self.workspace_root, self.work_ref.class_id, self.work_ref.work_id
        )
        if self.work_ref != expected.work_ref:
            raise QuillanRecordContextError("Assignment path work_ref is not canonical.")
        actual = (
            self.work_root,
            self.assignment_path,
            self.submissions_dir,
            self.scans_dir,
            self.exports_dir,
        )
        canonical = (
            expected.work_root,
            expected.assignment_path,
            expected.submissions_dir,
            expected.scans_dir,
            expected.exports_dir,
        )
        if actual != canonical:
            raise QuillanRecordContextError("Assignment record paths are not canonical.")


@dataclass(frozen=True, slots=True)
class QuillanStudentRecordPaths:
    """Exact canonical record and export paths for one student."""

    workspace_root: Path
    work_ref: ModuleWorkRef
    student_id: str
    student_dir: Path
    submission_manifest_path: Path
    review_record_path: Path
    exports_dir: Path
    feedback_markdown_path: Path
    feedback_pdf_path: Path

    @property
    def assignment_relative_path(self) -> str:
        """Return the exact canonical workspace-relative assignment path."""
        return quillan_work_paths(
            Path(), self.work_ref.class_id, self.work_ref.work_id
        ).assignment_path.as_posix()

    @property
    def submission_relative_path(self) -> str:
        """Return the exact canonical workspace-relative manifest path."""
        return submission_manifest_path(
            Path(), self.work_ref, self.student_id
        ).as_posix()

    @property
    def review_relative_path(self) -> str:
        """Return the exact canonical workspace-relative review path."""
        return review_record_path(Path(), self.work_ref, self.student_id).as_posix()

    def __post_init__(self) -> None:
        _require_absolute_workspace_root(self.workspace_root)
        validate_identifier(self.student_id, "student_id")
        expected = (
            student_submission_dir(self.workspace_root, self.work_ref, self.student_id),
            submission_manifest_path(self.workspace_root, self.work_ref, self.student_id),
            review_record_path(self.workspace_root, self.work_ref, self.student_id),
            student_exports_dir(self.workspace_root, self.work_ref, self.student_id),
            feedback_markdown_path(self.workspace_root, self.work_ref, self.student_id),
            feedback_pdf_path(self.workspace_root, self.work_ref, self.student_id),
        )
        actual = (
            self.student_dir,
            self.submission_manifest_path,
            self.review_record_path,
            self.exports_dir,
            self.feedback_markdown_path,
            self.feedback_pdf_path,
        )
        if actual != expected:
            raise QuillanRecordContextError("Student record paths are not canonical.")


@dataclass(frozen=True, slots=True)
class QuillanAssignmentRecordContext:
    """One validated assignment and its immutable canonical path bundle."""

    paths: QuillanAssignmentRecordPaths
    assignment_record: LoadedJsonRecord

    @property
    def assignment(self) -> Mapping[str, JsonValue]:
        return self.assignment_record.value

    def __post_init__(self) -> None:
        if type(self.paths) is not QuillanAssignmentRecordPaths:
            raise QuillanRecordContextError("paths must be exact assignment record paths.")
        record = self.assignment_record
        if type(record) is not LoadedJsonRecord:
            raise QuillanRecordContextError("assignment_record must be a LoadedJsonRecord.")
        if record.path != self.paths.assignment_path:
            raise QuillanRecordContextError("Assignment snapshot path is not canonical.")
        expected_relative = self.paths.assignment_path.relative_to(
            self.paths.workspace_root
        ).as_posix()
        if record.relative_path != expected_relative:
            raise QuillanRecordContextError("Assignment snapshot relative path is not canonical.")
        try:
            validate_assignment_config(mutable_json_copy(record.value))
        except AssignmentConfigError as error:
            raise QuillanRecordContextError(str(error)) from error
        _validate_assignment_identity(record.value, self.paths.work_ref)


@dataclass(frozen=True, slots=True)
class QuillanStudentReviewContext:
    """One coherent assignment, submission, and optional review context."""

    assignment_context: QuillanAssignmentRecordContext
    paths: QuillanStudentRecordPaths
    submission_record: LoadedJsonRecord
    review_record: LoadedJsonRecord | None
    review_policy: ReviewLoadingPolicy

    @property
    def submission(self) -> Mapping[str, JsonValue]:
        return self.submission_record.value

    @property
    def review(self) -> Mapping[str, JsonValue] | None:
        return None if self.review_record is None else self.review_record.value

    def __post_init__(self) -> None:
        if type(self.assignment_context) is not QuillanAssignmentRecordContext:
            raise QuillanRecordContextError(
                "assignment_context must be an exact QuillanAssignmentRecordContext."
            )
        if type(self.paths) is not QuillanStudentRecordPaths:
            raise QuillanRecordContextError("paths must be exact student record paths.")
        if self.paths.workspace_root != self.assignment_context.paths.workspace_root:
            raise QuillanRecordContextError("Student and assignment workspace roots differ.")
        if self.paths.work_ref != self.assignment_context.paths.work_ref:
            raise QuillanRecordContextError("Student and assignment work identities differ.")
        if type(self.review_policy) is not ReviewLoadingPolicy:
            raise QuillanRecordContextError("review_policy must be a ReviewLoadingPolicy.")
        _validate_snapshot_path(
            self.submission_record,
            self.paths.submission_manifest_path,
            self.paths.workspace_root,
            "Submission",
        )
        _validate_student_identity(
            self.submission_record.value,
            self.paths.work_ref,
            self.paths.student_id,
            "Submission manifest",
        )
        try:
            validate_submission_manifest(mutable_json_copy(self.submission_record.value))
        except SubmissionManifestError as error:
            raise QuillanRecordContextError(str(error)) from error
        if self.review_record is None:
            if self.review_policy is ReviewLoadingPolicy.REVIEW_REQUIRED:
                raise QuillanRecordContextError(
                    "A required-review context cannot omit its review snapshot."
                )
            return
        if self.review_policy is ReviewLoadingPolicy.REVIEW_MUST_BE_ABSENT:
            raise QuillanRecordContextError(
                "A review-must-be-absent context cannot contain a review snapshot."
            )
        _validate_snapshot_path(
            self.review_record,
            self.paths.review_record_path,
            self.paths.workspace_root,
            "Review",
        )
        _validate_student_identity(
            self.review_record.value,
            self.paths.work_ref,
            self.paths.student_id,
            "Review record",
        )
        try:
            validate_review_record(mutable_json_copy(self.review_record.value))
        except ReviewRecordError as error:
            raise QuillanRecordContextError(str(error)) from error
        if self.review_record.value["assignment_path"] != self.paths.assignment_relative_path:
            raise QuillanRecordContextError("Review assignment_path is not canonical.")
        if (
            self.review_record.value["submission_manifest_path"]
            != self.paths.submission_relative_path
        ):
            raise QuillanRecordContextError(
                "Review submission_manifest_path is not canonical."
            )
        _validate_review_export_paths(self.review_record.value, self.paths)


def assignment_record_paths(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> QuillanAssignmentRecordPaths:
    """Construct and preflight one exact assignment path context."""
    if not isinstance(work_ref, ModuleWorkRef):
        raise QuillanRecordContextError("work_ref must be a ModuleWorkRef.")
    root = _canonical_workspace_root(workspace_root)
    expected_ref = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    if work_ref != expected_ref:
        raise QuillanRecordContextError("work_ref must be an exact Quillan work reference.")
    paths = quillan_work_paths(root, work_ref.class_id, work_ref.work_id)
    return QuillanAssignmentRecordPaths(
        workspace_root=root,
        work_ref=paths.work_ref,
        work_root=paths.work_root,
        assignment_path=paths.assignment_path,
        submissions_dir=paths.submissions_dir,
        scans_dir=paths.scans_dir,
        exports_dir=paths.exports_dir,
    )


def student_record_paths(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
) -> QuillanStudentRecordPaths:
    """Construct and preflight one exact student path context."""
    assignment_paths = assignment_record_paths(workspace_root, work_ref)
    root = assignment_paths.workspace_root
    validate_identifier(student_id, "student_id")
    try:
        preflight_work_file_destination(
            root, work_ref, Path("submissions") / student_id / "submission.json"
        )
        preflight_work_file_destination(
            root, work_ref, Path("submissions") / student_id / "review.json"
        )
        preflight_work_file_destination(
            root,
            work_ref,
            Path("submissions") / student_id / "exports" / "feedback.md",
        )
        preflight_work_file_destination(
            root,
            work_ref,
            Path("submissions") / student_id / "exports" / "feedback.pdf",
        )
    except QuillanWorkPathError as error:
        raise UnsafeRecordPathError(str(error)) from error
    return QuillanStudentRecordPaths(
        workspace_root=root,
        work_ref=work_ref,
        student_id=student_id,
        student_dir=student_submission_dir(root, work_ref, student_id),
        submission_manifest_path=submission_manifest_path(root, work_ref, student_id),
        review_record_path=review_record_path(root, work_ref, student_id),
        exports_dir=student_exports_dir(root, work_ref, student_id),
        feedback_markdown_path=feedback_markdown_path(root, work_ref, student_id),
        feedback_pdf_path=feedback_pdf_path(root, work_ref, student_id),
    )


def load_quillan_assignment_context(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> QuillanAssignmentRecordContext:
    """Load only the canonical module-qualified Quillan assignment record."""
    paths = assignment_record_paths(workspace_root, work_ref)
    try:
        preflight_work_file_destination(paths.workspace_root, work_ref, "assignment.json")
    except QuillanWorkPathError as error:
        raise UnsafeRecordPathError(str(error)) from error
    if not os.path.lexists(paths.assignment_path):
        raise MissingAssignmentError(
            f"Assignment config not found: {paths.assignment_path}"
        )
    try:
        assignment_record = _load_json_record(
            paths.assignment_path,
            paths.workspace_root,
            validate_assignment_config,
        )
    except (AssignmentConfigError, OSError, UnicodeError, ValueError) as error:
        raise InvalidAssignmentError(str(error)) from error
    _validate_assignment_identity(assignment_record.value, work_ref)
    return QuillanAssignmentRecordContext(paths, assignment_record)


def load_quillan_student_review_context(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    student_id: str,
    *,
    review_policy: ReviewLoadingPolicy = ReviewLoadingPolicy.REVIEW_OPTIONAL,
) -> QuillanStudentReviewContext:
    """Load one coherent canonical student context under an explicit review policy."""
    if not isinstance(review_policy, ReviewLoadingPolicy):
        raise QuillanRecordContextError("review_policy must be a ReviewLoadingPolicy.")
    assignment_context = load_quillan_assignment_context(workspace_root, work_ref)
    paths = student_record_paths(
        assignment_context.paths.workspace_root, work_ref, student_id
    )
    manifest_exists = os.path.lexists(paths.submission_manifest_path)
    review_exists = os.path.lexists(paths.review_record_path)
    if not manifest_exists:
        if review_exists:
            raise OrphanReviewError(
                "A review record exists without its canonical submission manifest."
            )
        raise MissingSubmissionError(
            f"Submission manifest not found: {paths.submission_manifest_path}"
        )
    try:
        submission_record = _load_json_record(
            paths.submission_manifest_path,
            paths.workspace_root,
            validate_submission_manifest,
        )
    except (SubmissionManifestError, OSError, UnicodeError, ValueError) as error:
        raise InvalidSubmissionError(str(error)) from error
    _validate_student_identity(
        submission_record.value, work_ref, student_id, "Submission manifest"
    )

    review_record: LoadedJsonRecord | None = None
    if review_exists:
        if review_policy is ReviewLoadingPolicy.REVIEW_MUST_BE_ABSENT:
            raise ReviewAlreadyExistsError(
                f"Review record already exists: {paths.review_record_path}"
            )
        try:
            review_record = _load_json_record(
                paths.review_record_path,
                paths.workspace_root,
                validate_review_record,
            )
        except (ReviewRecordError, OSError, UnicodeError, ValueError) as error:
            raise InvalidReviewError(
                str(error), submission_record=submission_record
            ) from error
        review_value = review_record.value
        _validate_student_identity(review_value, work_ref, student_id, "Review record")
        if review_value["assignment_path"] != paths.assignment_relative_path:
            raise InvalidReviewError(
                "Review assignment_path is not canonical.",
                submission_record=submission_record,
            )
        if review_value["submission_manifest_path"] != paths.submission_relative_path:
            raise InvalidReviewError(
                "Review submission_manifest_path is not canonical.",
                submission_record=submission_record,
            )
        try:
            _validate_review_export_paths(review_value, paths)
        except InvalidReviewError as error:
            raise InvalidReviewError(
                str(error), submission_record=submission_record
            ) from error
    elif review_policy is ReviewLoadingPolicy.REVIEW_REQUIRED:
        raise MissingReviewError(f"Review record not found: {paths.review_record_path}")

    return QuillanStudentReviewContext(
        assignment_context=assignment_context,
        paths=paths,
        submission_record=submission_record,
        review_record=review_record,
        review_policy=review_policy,
    )


def mutable_json_copy(value: Mapping[str, JsonValue]) -> dict[str, Any]:
    """Return an isolated mutable JSON-native copy of an immutable context record."""
    return cast(dict[str, Any], _thaw(value))


def canonical_workspace_root(workspace_root: str | Path) -> Path:
    """Validate and return the supplied existing non-link workspace root."""
    return _canonical_workspace_root(workspace_root)


def _canonical_workspace_root(workspace_root: str | Path) -> Path:
    if not isinstance(workspace_root, (str, Path)):
        raise QuillanRecordContextError("workspace_root must be a string or Path.")
    root = Path(os.path.abspath(Path(workspace_root)))
    _require_absolute_workspace_root(root)
    if not os.path.lexists(root):
        raise UnsafeRecordPathError(f"Workspace root does not exist: {root}")
    if _is_link_like(root) or not root.is_dir():
        raise UnsafeRecordPathError(
            f"Workspace root must be an ordinary non-link directory: {root}"
        )
    return root


def _require_absolute_workspace_root(root: Path) -> None:
    if not isinstance(root, Path) or not root.is_absolute():
        raise QuillanRecordContextError("workspace_root must be an absolute Path.")
    if root != Path(os.path.abspath(root)):
        raise QuillanRecordContextError("workspace_root must be canonical.")


def _validate_student_identity(
    record: Mapping[str, Any],
    work_ref: ModuleWorkRef,
    student_id: str,
    record_name: str,
) -> None:
    expected = {
        "class_id": work_ref.class_id,
        "assignment_id": work_ref.work_id,
        "student_id": student_id,
    }
    for field, identity in expected.items():
        if record[field] != identity:
            raise RecordIdentityMismatchError(
                f"{record_name} {field} is {record[field]!r}, expected {identity!r}."
            )


def _validate_assignment_identity(
    assignment: Mapping[str, Any], work_ref: ModuleWorkRef
) -> None:
    if assignment["assignment_id"] != work_ref.work_id:
        raise RecordIdentityMismatchError(
            "Path assignment_id does not match assignment config assignment_id."
        )
    class_ids = assignment["class_ids"]
    if not isinstance(class_ids, (list, tuple)) or work_ref.class_id not in class_ids:
        raise RecordIdentityMismatchError(
            f"Class {work_ref.class_id!r} is not included in assignment "
            f"{work_ref.work_id!r}."
        )


def _validate_snapshot_path(
    record: LoadedJsonRecord,
    path: Path,
    workspace_root: Path,
    name: str,
) -> None:
    if type(record) is not LoadedJsonRecord:
        raise QuillanRecordContextError(f"{name} record must be a LoadedJsonRecord.")
    if record.path != path:
        raise QuillanRecordContextError(f"{name} snapshot path is not canonical.")
    if record.relative_path != path.relative_to(workspace_root).as_posix():
        raise QuillanRecordContextError(
            f"{name} snapshot relative path is not canonical."
        )


def _load_json_record(
    path: Path,
    workspace_root: Path,
    validator: Any,
) -> LoadedJsonRecord:
    try:
        _preflight_arbitrary_file_destination(path)
    except QuillanWorkPathError as error:
        raise UnsafeRecordPathError(str(error)) from error
    try:
        original_bytes = path.read_bytes()
    except OSError:
        raise
    value = _strict_json_object(original_bytes, path)
    validator(value)
    return LoadedJsonRecord(
        path=path,
        relative_path=path.relative_to(workspace_root).as_posix(),
        original_bytes=original_bytes,
        value=_freeze_mapping(value),
    )


def _strict_json_object(data: bytes, path: Path) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON object key {key!r}: {path}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ValueError(f"Invalid JSON constant {value!r}: {path}")

    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Record is not valid JSON (strict UTF-8): {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ValueError(f"Record must be a JSON object: {path}")
    return cast(dict[str, Any], value)


def _validate_review_export_paths(
    review: Mapping[str, Any],
    paths: QuillanStudentRecordPaths,
) -> None:
    exports = review.get("exports")
    if not isinstance(exports, Mapping):
        return
    expected = {
        "feedback_markdown": paths.feedback_markdown_path.relative_to(
            paths.workspace_root
        ).as_posix(),
        "feedback_pdf": paths.feedback_pdf_path.relative_to(
            paths.workspace_root
        ).as_posix(),
    }
    for field, canonical_path in expected.items():
        metadata = exports.get(field)
        if isinstance(metadata, Mapping) and metadata.get("path") != canonical_path:
            raise InvalidReviewError(f"Review exports.{field}.path is not canonical.")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, JsonValue]:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> JsonValue:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise QuillanRecordContextError("Loaded record contains a non-JSON value.")


def _thaw(value: JsonValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _is_recursively_frozen(value: Any) -> bool:
    if type(value) is type(MappingProxyType({})):
        mapping = cast(Mapping[str, Any], value)
        return all(
            type(key) is str and _is_recursively_frozen(item)
            for key, item in mapping.items()
        )
    if type(value) is tuple:
        return all(_is_recursively_frozen(item) for item in value)
    if value is None or type(value) in {str, int, float, bool}:
        return not (type(value) is float and (value != value or abs(value) == float("inf")))
    return False


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


__all__ = [
    "InvalidAssignmentError",
    "InvalidReviewError",
    "InvalidSubmissionError",
    "JsonValue",
    "LoadedJsonRecord",
    "MissingAssignmentError",
    "MissingReviewError",
    "MissingSubmissionError",
    "OrphanReviewError",
    "QuillanAssignmentRecordContext",
    "QuillanAssignmentRecordPaths",
    "QuillanRecordContextError",
    "QuillanStudentRecordPaths",
    "QuillanStudentReviewContext",
    "RecordIdentityMismatchError",
    "ReviewAlreadyExistsError",
    "ReviewLoadingPolicy",
    "UnsafeRecordPathError",
    "assignment_record_paths",
    "canonical_workspace_root",
    "load_quillan_assignment_context",
    "load_quillan_student_review_context",
    "mutable_json_copy",
    "student_record_paths",
]

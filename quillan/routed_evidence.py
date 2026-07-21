"""Materialize page-specific evidence only from Core-retained scan bytes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Final

import cv2
from pds_core.routing_models import ModuleWorkRef
from pds_core.scan_retention import RetainedSourceScan

from quillan.module_errors import (
    QuillanModuleError,
    QuillanRoutedEvidenceError,
    QuillanRoutedEvidenceIntegrityError,
    QuillanRoutedEvidenceMissingError,
    QuillanRoutedEvidencePathError,
)
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.retained_scan_pages import (
    SUPPORTED_IMAGE_EXTENSIONS,
    load_retained_page_for_qr,
)
from quillan.retained_source import validate_quillan_retained_source
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_ref,
    routed_evidence_path,
)

_COPY_BUFFER_SIZE: Final[int] = 1024 * 1024
_OBSERVATION_ID: Final[re.Pattern[str]] = re.compile(r"^obs_[0-9a-f]{32}$")
_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class _PreparedRoutedPageEvidence:
    """Complete evidence content and destination before filesystem mutation."""

    workspace_root: Path
    observation_id: str
    path: Path
    relative_path: str
    sha256: str
    size_bytes: int
    extension: str
    evidence_kind: str
    content: bytes

    def __post_init__(self) -> None:
        _validate_prepared(self)


@dataclass(frozen=True, slots=True)
class RoutedPageEvidence:
    """A safely installed routed page-evidence artifact."""

    workspace_root: Path
    observation_id: str
    path: Path
    relative_path: str
    sha256: str
    size_bytes: int
    extension: str
    evidence_kind: str
    created_by_current_operation: bool

    def __post_init__(self) -> None:
        _validate_evidence_fields(
            self.workspace_root,
            self.observation_id,
            self.path,
            self.relative_path,
            self.sha256,
            self.size_bytes,
            self.extension,
            self.evidence_kind,
        )
        if type(self.created_by_current_operation) is not bool:
            raise QuillanRoutedEvidenceError(
                "created_by_current_operation must be a Boolean."
            )

    @property
    def absolute_path(self) -> Path:
        return self.path

    @property
    def workspace_relative_path(self) -> str:
        return self.relative_path


def _prepare_routed_page_evidence(
    workspace_root: Path,
    result: QuillanResponsePageDispatchResult,
    *,
    observation_id: str,
) -> _PreparedRoutedPageEvidence:
    """Render or copy the complete evidence bytes without filesystem mutation."""
    root = _workspace_root(workspace_root)
    try:
        validated = validate_quillan_response_page_dispatch_result(result)
        retained = _retained_source(validated)
        validate_quillan_retained_source(
            retained,
            workspace_root=root,
            source_page_number=validated.source_page_number,
        )
        suffix = validated.retained_source_path.suffix.lower()
        if suffix in SUPPORTED_IMAGE_EXTENSIONS:
            if validated.source_page_number != 1:
                raise QuillanRoutedEvidenceError(
                    "Image retained sources contain only physical page one."
                )
            content = _read_exact_bytes(validated.retained_source_path)
            extension = suffix
            evidence_kind = "retained_image_copy"
        elif suffix == ".pdf":
            image = load_retained_page_for_qr(
                retained,
                validated.source_page_number,
                workspace_root=root,
            )
            encoded, png = cv2.imencode(".png", image)
            if not encoded or png.size == 0:
                raise QuillanRoutedEvidenceError(
                    "Converted retained PDF page could not be encoded as PNG."
                )
            content = png.tobytes()
            extension = ".png"
            evidence_kind = "rendered_pdf_page_png"
        else:
            raise QuillanRoutedEvidenceError("Unsupported retained-source extension.")
        if not content:
            raise QuillanRoutedEvidenceError("Routed evidence must not be empty.")
        work_ref = quillan_work_ref(validated.class_id, validated.assignment_id)
        destination = routed_evidence_path(
            root,
            work_ref,
            validated.issuance_id,
            validated.student_id,
            validated.logical_page,
            observation_id,
            extension,
        )
        relative = destination.relative_to(root).as_posix()
        return _PreparedRoutedPageEvidence(
            workspace_root=root,
            observation_id=observation_id,
            path=destination,
            relative_path=relative,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            extension=extension,
            evidence_kind=evidence_kind,
            content=content,
        )
    except QuillanRoutedEvidenceError:
        raise
    except (QuillanModuleError, ValueError, TypeError, OSError, cv2.error) as error:
        raise QuillanRoutedEvidenceError(
            f"Could not prepare routed page evidence: {error}"
        ) from error


def _install_prepared_routed_page_evidence(
    workspace_root: Path,
    result: QuillanResponsePageDispatchResult,
    prepared: _PreparedRoutedPageEvidence,
) -> RoutedPageEvidence:
    """Exclusively install and reopen-verify prepared evidence bytes."""
    root = _workspace_root(workspace_root)
    validated = validate_quillan_response_page_dispatch_result(result)
    if type(prepared) is not _PreparedRoutedPageEvidence:
        raise QuillanRoutedEvidenceError("prepared has the wrong type.")
    _validate_prepared(prepared)
    work_ref = quillan_work_ref(validated.class_id, validated.assignment_id)
    try:
        expected_extension, expected_kind = _evidence_format(validated)
        expected_path = routed_evidence_path(
            root,
            work_ref,
            validated.issuance_id,
            validated.student_id,
            validated.logical_page,
            prepared.observation_id,
            expected_extension,
        )
        if (
            prepared.workspace_root != root
            or prepared.path != expected_path
            or prepared.relative_path != expected_path.relative_to(root).as_posix()
            or prepared.extension != expected_extension
            or prepared.evidence_kind != expected_kind
        ):
            raise QuillanRoutedEvidenceError(
                "Prepared evidence destination contradicts dispatch authority."
            )
        preflight_work_directory_destination(
            root,
            work_ref,
            Path("scans") / "evidence" / validated.issuance_id,
        )
        preflight_work_file_destination(
            root,
            work_ref,
            prepared.path.relative_to(
                root
                / "classes"
                / validated.class_id
                / "modules"
                / "quillan"
                / "work"
                / validated.assignment_id
            ),
        )
        prepared.path.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(prepared.path, prepared.content)
        _verify_installed(prepared)
    except FileExistsError as error:
        raise QuillanRoutedEvidenceError(
            f"Routed evidence destination already exists: {prepared.path}"
        ) from error
    except (OSError, QuillanWorkPathError) as error:
        raise QuillanRoutedEvidenceError(
            f"Could not install routed page evidence: {error}"
        ) from error
    return _installed_result(prepared, created=True)


def materialize_routed_page_evidence(
    workspace_root: Path,
    result: QuillanResponsePageDispatchResult,
    *,
    observation_id: str,
) -> RoutedPageEvidence:
    """Prepare and exclusively install one routed evidence artifact."""
    prepared = _prepare_routed_page_evidence(
        workspace_root, result, observation_id=observation_id
    )
    return _install_prepared_routed_page_evidence(workspace_root, result, prepared)


def verify_contextual_routed_page_evidence(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    *,
    issuance_id: str,
    student_id: str,
    logical_page: int,
    observation_id: str,
    extension: str,
    relative_path: str,
    expected_sha256: str,
    expected_size_bytes: int,
) -> Path:
    """Recompute, preflight, and verify one canonical routed-evidence file."""
    root = _workspace_root(workspace_root)
    expected = routed_evidence_path(
        root,
        work_ref,
        issuance_id,
        student_id,
        logical_page,
        observation_id,
        extension,
    )
    expected_relative = expected.relative_to(root).as_posix()
    if (
        type(relative_path) is not str
        or PurePosixPath(relative_path).as_posix() != relative_path
        or relative_path != expected_relative
    ):
        raise QuillanRoutedEvidencePathError(
            "Routed evidence path is not the canonical observation destination."
        )
    work_root = (
        root
        / "classes"
        / work_ref.class_id
        / "modules"
        / "quillan"
        / "work"
        / work_ref.work_id
    )
    try:
        preflight_work_file_destination(
            root, work_ref, expected.relative_to(work_root)
        )
    except QuillanWorkPathError as error:
        raise QuillanRoutedEvidencePathError(str(error)) from error
    if not os.path.lexists(expected):
        raise QuillanRoutedEvidenceMissingError(
            f"Routed evidence is missing: {expected}"
        )
    if _is_link_like(expected) or not expected.is_file():
        raise QuillanRoutedEvidencePathError(
            f"Routed evidence must be an ordinary non-link file: {expected}"
        )
    verify_routed_page_evidence(
        expected,
        expected_sha256=expected_sha256,
        expected_size_bytes=expected_size_bytes,
    )
    return expected


def verify_routed_page_evidence(
    path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int,
) -> None:
    """Verify an ordinary non-link evidence file against immutable metadata."""
    if not isinstance(path, Path):
        raise QuillanRoutedEvidenceError("Evidence path must be a Path.")
    if not os.path.lexists(path):
        raise QuillanRoutedEvidenceMissingError(f"Routed evidence is missing: {path}")
    if _is_link_like(path) or not path.is_file():
        raise QuillanRoutedEvidenceIntegrityError(
            f"Routed evidence must be an ordinary non-link file: {path}"
        )
    content = _read_exact_bytes(path)
    if len(content) != expected_size_bytes:
        raise QuillanRoutedEvidenceIntegrityError(
            "Routed evidence size does not match metadata."
        )
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise QuillanRoutedEvidenceIntegrityError(
            "Routed evidence hash does not match metadata."
        )


def _workspace_root(value: object) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise QuillanRoutedEvidenceError("workspace_root must be an absolute Path.")
    root = Path(os.path.abspath(value))
    if value != root or _is_link_like(root) or not root.is_dir():
        raise QuillanRoutedEvidenceError(
            "workspace_root must be an existing canonical non-link directory."
        )
    return root


def _retained_source(result: QuillanResponsePageDispatchResult) -> RetainedSourceScan:
    return RetainedSourceScan(
        source_scan_id=result.source_scan_id,
        source_filename=result.source_filename,
        source_sha256=result.source_sha256,
        retained_source_path=result.retained_source_path,
        retained_source_relative_path=result.retained_source_relative_path,
        intake_timestamp=result.intake_timestamp,
        intake_date=result.intake_date,
    )


def _read_exact_bytes(path: Path) -> bytes:
    if _is_link_like(path) or not path.is_file():
        raise QuillanRoutedEvidenceError(f"Source is not an ordinary file: {path}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise QuillanRoutedEvidenceError(
            f"Could not read file {path}: {error}"
        ) from error


def _write_exclusive(path: Path, content: bytes) -> None:
    with path.open("xb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())


def _verify_installed(prepared: _PreparedRoutedPageEvidence) -> None:
    verify_routed_page_evidence(
        prepared.path,
        expected_sha256=prepared.sha256,
        expected_size_bytes=prepared.size_bytes,
    )
    if _read_exact_bytes(prepared.path) != prepared.content:
        raise QuillanRoutedEvidenceError(
            "Installed routed evidence bytes differ from prepared content."
        )


def _installed_result(
    prepared: _PreparedRoutedPageEvidence, *, created: bool
) -> RoutedPageEvidence:
    return RoutedPageEvidence(
        workspace_root=prepared.workspace_root,
        observation_id=prepared.observation_id,
        path=prepared.path,
        relative_path=prepared.relative_path,
        sha256=prepared.sha256,
        size_bytes=prepared.size_bytes,
        extension=prepared.extension,
        evidence_kind=prepared.evidence_kind,
        created_by_current_operation=created,
    )


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


def _evidence_format(
    result: QuillanResponsePageDispatchResult,
) -> tuple[str, str]:
    suffix = result.retained_source_path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        return suffix, "retained_image_copy"
    if suffix == ".pdf":
        return ".png", "rendered_pdf_page_png"
    raise QuillanRoutedEvidenceError("Unsupported retained-source extension.")


def _validate_evidence_fields(
    workspace_root: object,
    observation_id: object,
    path: object,
    relative_path: object,
    sha256: object,
    size_bytes: object,
    extension: object,
    evidence_kind: object,
) -> None:
    if (
        not isinstance(workspace_root, Path)
        or not workspace_root.is_absolute()
        or Path(os.path.abspath(workspace_root)) != workspace_root
        or _is_link_like(workspace_root)
        or not workspace_root.is_dir()
    ):
        raise QuillanRoutedEvidenceError(
            "Evidence workspace_root must be a canonical non-link directory."
        )
    if type(observation_id) is not str or _OBSERVATION_ID.fullmatch(observation_id) is None:
        raise QuillanRoutedEvidenceError("Invalid routed-evidence observation_id.")
    if not isinstance(path, Path) or not path.is_absolute() or Path(os.path.abspath(path)) != path:
        raise QuillanRoutedEvidenceError("Evidence path must be canonical and absolute.")
    if type(relative_path) is not str or not relative_path or "\\" in relative_path:
        raise QuillanRoutedEvidenceError("Evidence relative_path must be POSIX text.")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or relative.as_posix() != relative_path or ".." in relative.parts:
        raise QuillanRoutedEvidenceError("Evidence relative_path must be canonical.")
    try:
        actual_relative = path.relative_to(workspace_root).as_posix()
    except ValueError as error:
        raise QuillanRoutedEvidenceError(
            "Evidence path must be contained by workspace_root."
        ) from error
    if actual_relative != relative_path:
        raise QuillanRoutedEvidenceError("Evidence paths disagree.")
    if type(sha256) is not str or _SHA256.fullmatch(sha256) is None:
        raise QuillanRoutedEvidenceError("Invalid evidence SHA-256.")
    if type(size_bytes) is not int or isinstance(size_bytes, bool) or size_bytes < 1:
        raise QuillanRoutedEvidenceError("Evidence size must be positive.")
    if type(extension) is not str or extension != extension.lower() or not extension.startswith("."):
        raise QuillanRoutedEvidenceError("Invalid evidence extension.")
    if path.suffix.lower() != extension or relative.suffix.lower() != extension:
        raise QuillanRoutedEvidenceError("Evidence extension contradicts its paths.")
    allowed = {
        "retained_image_copy": SUPPORTED_IMAGE_EXTENSIONS,
        "rendered_pdf_page_png": frozenset({".png"}),
    }
    if evidence_kind not in allowed or extension not in allowed[evidence_kind]:
        raise QuillanRoutedEvidenceError("Unsupported evidence kind or extension.")


def _validate_prepared(prepared: _PreparedRoutedPageEvidence) -> None:
    try:
        _validate_evidence_fields(
            prepared.workspace_root,
            prepared.observation_id,
            prepared.path,
            prepared.relative_path,
            prepared.sha256,
            prepared.size_bytes,
            prepared.extension,
            prepared.evidence_kind,
        )
        content = prepared.content
        size_bytes = prepared.size_bytes
        sha256 = prepared.sha256
    except AttributeError as error:
        raise QuillanRoutedEvidenceError(
            "Prepared evidence is missing required internal state."
        ) from error
    if type(content) is not bytes or not content:
        raise QuillanRoutedEvidenceError("Prepared evidence content must be bytes.")
    if len(content) != size_bytes:
        raise QuillanRoutedEvidenceError("Prepared evidence size is inconsistent.")
    if hashlib.sha256(content).hexdigest() != sha256:
        raise QuillanRoutedEvidenceError("Prepared evidence hash is inconsistent.")


__all__ = [
    "RoutedPageEvidence",
    "materialize_routed_page_evidence",
    "verify_contextual_routed_page_evidence",
    "verify_routed_page_evidence",
]

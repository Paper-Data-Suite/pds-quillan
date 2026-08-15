"""Authorization-gated Quillan Academic Result artifact resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, Literal, Protocol, TypeAlias, cast

from quillan._path_safety import is_link_like
from quillan.academic_result_manifest import (
    AcademicResultManifest,
    EvidenceReference,
    WorkReference,
)
from quillan.academic_result_reader import (
    QuillanAcademicResultReaderError,
    lookup_academic_result_student,
    validate_academic_result_manifest,
)
from quillan.record_context import (
    QuillanRecordContextError,
    canonical_workspace_root,
)
from quillan.review_record import ReviewRecordError, validate_review_record
from quillan.submission_manifest import (
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    feedback_markdown_path,
    feedback_pdf_path,
    quillan_work_paths,
    quillan_work_ref,
    review_record_path,
    routed_evidence_path,
    submission_manifest_path,
)

AcademicResultArtifactKind: TypeAlias = Literal[
    "student_work",
    "feedback_pdf",
    "feedback_markdown",
]
ArtifactAuthorizationStatus: TypeAlias = Literal["allowed", "denied", "unresolved"]

_ALLOWED_ARTIFACT_KINDS: Final[frozenset[str]] = frozenset(
    {"student_work", "feedback_pdf", "feedback_markdown"}
)
_ALLOWED_AUTHORIZATION_STATES: Final[frozenset[str]] = frozenset(
    {"allowed", "denied", "unresolved"}
)
_MAX_PURPOSE = 500
_SHA256 = frozenset("0123456789abcdef")


class QuillanAcademicResultArtifactError(Exception):
    """Base failure for authorized Academic Result artifact access."""


class QuillanAcademicResultArtifactValidationError(
    QuillanAcademicResultArtifactError, ValueError
):
    """Artifact request or public input is invalid."""


class QuillanAcademicResultArtifactAuthorizationError(
    QuillanAcademicResultArtifactError, PermissionError
):
    """Artifact authorization was denied, unresolved, or invalid."""


class QuillanAcademicResultArtifactUnavailableError(
    QuillanAcademicResultArtifactError, LookupError
):
    """The authorized exact artifact has no available producer representation."""


class QuillanAcademicResultArtifactIntegrityError(
    QuillanAcademicResultArtifactError
):
    """Producer source or artifact state contradicts the manifest."""


class QuillanAcademicResultArtifactReadError(
    QuillanAcademicResultArtifactError, OSError
):
    """An otherwise valid authorized source or artifact could not be read."""


@dataclass(frozen=True, slots=True)
class AcademicResultArtifactAuthorizationRequest:
    """Privacy-bounded exact request supplied to deployment authorization."""

    work: WorkReference
    record_set_id: str
    record_set_revision: int
    student_id: str
    artifact_kind: AcademicResultArtifactKind
    purpose: str


@dataclass(frozen=True, slots=True)
class AcademicResultArtifactAuthorizationDecision:
    """Deployment-owned authorization result; absence of allow is not permission."""

    status: ArtifactAuthorizationStatus

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_AUTHORIZATION_STATES:
            raise QuillanAcademicResultArtifactValidationError(
                "Authorization decision status is invalid."
            )


class AcademicResultArtifactAuthorizationGate(Protocol):
    """External authorization boundary supplied by the deployment/application."""

    def authorize(
        self,
        request: AcademicResultArtifactAuthorizationRequest,
    ) -> AcademicResultArtifactAuthorizationDecision:
        """Return an explicit allowed, denied, or unresolved decision."""


@dataclass(frozen=True, slots=True)
class AuthorizedAcademicResultArtifact:
    """One immutable exact artifact returned after authorization and verification."""

    artifact_kind: AcademicResultArtifactKind
    work: WorkReference
    record_set_revision: int
    student_id: str
    relative_path: str
    media_type: str
    sha256: str
    byte_size: int
    data: bytes
    evidence_reference: EvidenceReference | None = None
    generated_at: str | None = None
    source_review_updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.artifact_kind not in _ALLOWED_ARTIFACT_KINDS:
            raise QuillanAcademicResultArtifactValidationError(
                "Authorized artifact kind is invalid."
            )
        if type(self.data) is not bytes:
            raise QuillanAcademicResultArtifactValidationError(
                "Authorized artifact data must be immutable bytes."
            )
        if self.byte_size != len(self.data):
            raise QuillanAcademicResultArtifactValidationError(
                "Authorized artifact byte_size disagrees with data."
            )
        if (
            len(self.sha256) != 64
            or any(character not in _SHA256 for character in self.sha256)
            or hashlib.sha256(self.data).hexdigest() != self.sha256
        ):
            raise QuillanAcademicResultArtifactValidationError(
                "Authorized artifact SHA-256 disagrees with data."
            )
        _workspace_relative_posix(self.relative_path, "relative_path")


class _DuplicateJsonKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value}")


def _strict_json_object(
    value: bytes,
    *,
    source_name: Literal["submission", "review"],
) -> dict[str, object]:
    try:
        decoded = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            f"Manifest-bound {source_name} source is not valid strict JSON."
        ) from error
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise QuillanAcademicResultArtifactIntegrityError(
            f"Manifest-bound {source_name} source is not one JSON object."
        )
    return cast(dict[str, object], decoded)


def _purpose(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_PURPOSE
        or "\x00" in value
    ):
        raise QuillanAcademicResultArtifactValidationError(
            f"purpose must be nonempty bounded text of at most {_MAX_PURPOSE} characters."
        )
    return value


def _artifact_kind(value: object) -> AcademicResultArtifactKind:
    if not isinstance(value, str) or value not in _ALLOWED_ARTIFACT_KINDS:
        raise QuillanAcademicResultArtifactValidationError(
            "artifact_kind must be student_work, feedback_pdf, or feedback_markdown."
        )
    return cast(AcademicResultArtifactKind, value)


def _authorize(
    gate: AcademicResultArtifactAuthorizationGate,
    request: AcademicResultArtifactAuthorizationRequest,
) -> None:
    authorize = getattr(gate, "authorize", None)
    if not callable(authorize):
        raise QuillanAcademicResultArtifactAuthorizationError(
            "Artifact authorization gate is unavailable."
        )
    try:
        decision = authorize(request)
    except Exception as error:
        raise QuillanAcademicResultArtifactAuthorizationError(
            "Artifact authorization could not be established."
        ) from error
    if type(decision) is not AcademicResultArtifactAuthorizationDecision:
        raise QuillanAcademicResultArtifactAuthorizationError(
            "Artifact authorization decision is invalid."
        )
    if decision.status != "allowed":
        raise QuillanAcademicResultArtifactAuthorizationError(
            "Artifact access is not authorized."
        )


def _workspace_relative_posix(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise QuillanAcademicResultArtifactIntegrityError(
            f"{field} must be canonical workspace-relative POSIX text."
        )
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or value != posix.as_posix()
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise QuillanAcademicResultArtifactIntegrityError(
            f"{field} must be canonical workspace-relative POSIX text."
        )
    return value


def _require_non_link_path_chain(workspace_root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(workspace_root)
    except ValueError as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized producer path escapes the workspace."
        ) from error
    current = workspace_root
    for component in relative.parts:
        current = current / component
        if os.path.lexists(current) and is_link_like(current):
            raise QuillanAcademicResultArtifactIntegrityError(
                "Authorized producer path contains a link-like component."
            )


def _read_regular_file(
    path: Path,
    *,
    workspace_root: Path,
    missing_message: str,
) -> bytes:
    try:
        _require_non_link_path_chain(workspace_root, path)
        if not os.path.lexists(path):
            raise QuillanAcademicResultArtifactUnavailableError(missing_message)
        if not path.is_file():
            raise QuillanAcademicResultArtifactIntegrityError(
                "Authorized producer artifact path is not an ordinary regular file."
            )
        return path.read_bytes()
    except QuillanAcademicResultArtifactError:
        raise
    except OSError as error:
        raise QuillanAcademicResultArtifactReadError(
            "Authorized producer artifact could not be read."
        ) from error


def _load_bound_submission(
    workspace_root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
) -> dict[str, object]:
    student = lookup_academic_result_student(manifest, student_id)
    work_ref = quillan_work_ref(manifest.work.class_id, manifest.work.work_id)
    paths = quillan_work_paths(
        workspace_root, manifest.work.class_id, manifest.work.work_id
    )
    snapshot = student.source_snapshot.submission
    expected_source = f"submissions/{student_id}/submission.json"
    if snapshot.relative_path != expected_source:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest submission source path is not canonical for the represented student."
        )
    exact_path = paths.work_root.joinpath(*PurePosixPath(snapshot.relative_path).parts)
    canonical_path = submission_manifest_path(workspace_root, work_ref, student_id)
    if exact_path != canonical_path:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest submission source path disagrees with Quillan canonical storage."
        )
    raw = _read_regular_file(
        exact_path,
        workspace_root=workspace_root,
        missing_message="Manifest-bound submission source is unavailable.",
    )
    if hashlib.sha256(raw).hexdigest() != snapshot.sha256:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound submission source bytes have changed."
        )
    source = _strict_json_object(raw, source_name="submission")
    try:
        validate_submission_manifest(source)
    except (SubmissionManifestError, TypeError, ValueError) as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound submission source violates the Quillan submission contract."
        ) from error
    expected_identity = (
        manifest.work.class_id,
        manifest.work.work_id,
        student_id,
    )
    if (
        source.get("class_id"),
        source.get("assignment_id"),
        source.get("student_id"),
    ) != expected_identity:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound submission identity disagrees with the requested result."
        )
    return source


def _load_bound_review(
    workspace_root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
) -> dict[str, object]:
    student = lookup_academic_result_student(manifest, student_id)
    work_ref = quillan_work_ref(manifest.work.class_id, manifest.work.work_id)
    paths = quillan_work_paths(
        workspace_root, manifest.work.class_id, manifest.work.work_id
    )
    snapshot = student.source_snapshot.review
    expected_source = f"submissions/{student_id}/review.json"
    if snapshot.relative_path != expected_source:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest review source path is not canonical for the represented student."
        )
    exact_path = paths.work_root.joinpath(*PurePosixPath(snapshot.relative_path).parts)
    canonical_path = review_record_path(workspace_root, work_ref, student_id)
    if exact_path != canonical_path:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest review source path disagrees with Quillan canonical storage."
        )
    raw = _read_regular_file(
        exact_path,
        workspace_root=workspace_root,
        missing_message="Manifest-bound review source is unavailable.",
    )
    if hashlib.sha256(raw).hexdigest() != snapshot.sha256:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound review source bytes have changed."
        )
    source = _strict_json_object(raw, source_name="review")
    try:
        validate_review_record(source)
    except (ReviewRecordError, TypeError, ValueError) as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound review source violates the Quillan review contract."
        ) from error
    expected_identity = (
        manifest.work.class_id,
        manifest.work.work_id,
        student_id,
    )
    if (
        source.get("class_id"),
        source.get("assignment_id"),
        source.get("student_id"),
    ) != expected_identity:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest-bound review identity disagrees with the requested result."
        )
    return source


def _as_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise QuillanAcademicResultArtifactIntegrityError(
            f"{context} is not an object."
        )
    return cast(Mapping[str, object], value)


def _as_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise QuillanAcademicResultArtifactIntegrityError(
            f"{context} is not an array."
        )
    return cast(list[object], value)


def _native_selected_evidence(
    submission: Mapping[str, object],
    reference: EvidenceReference,
) -> tuple[Mapping[str, object], int]:
    matches: list[tuple[Mapping[str, object], Mapping[str, object], int]] = []
    for page_value in _as_list(submission.get("pages"), "submission.pages"):
        page = _as_mapping(page_value, "submission page")
        page_number = page.get("page_number")
        if isinstance(page_number, bool) or not isinstance(page_number, int):
            raise QuillanAcademicResultArtifactIntegrityError(
                "Submission page_number is invalid."
            )
        for evidence_value in _as_list(page.get("evidence"), "submission page evidence"):
            evidence = _as_mapping(evidence_value, "submission evidence")
            if evidence.get("evidence_id") == reference.evidence_id:
                matches.append((page, evidence, page_number))
    if len(matches) != 1:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest evidence reference does not resolve to one native evidence row."
        )
    page, evidence, page_number = matches[0]
    if page.get("selected_evidence_id") != reference.evidence_id:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest evidence is no longer the authoritative selected page evidence."
        )
    if evidence.get("evidence_role") != "selected":
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest evidence does not have the native selected evidence role."
        )
    details = _as_mapping(evidence.get("module_details"), "evidence.module_details")
    retained = _as_mapping(evidence.get("retained_source"), "evidence.retained_source")
    expected_pairs = (
        (details.get("page_id"), reference.page_id),
        (evidence.get("evidence_id"), reference.evidence_id),
        (details.get("observation_id"), reference.observation_id),
        (details.get("route_id"), reference.route_id),
        (details.get("issuance_id"), reference.issuance_id),
        (details.get("generation_id"), reference.generation_id),
        (details.get("artifact_id"), reference.artifact_id),
        (retained.get("source_page_number"), reference.source_page_number),
        (retained.get("source_scan_id"), reference.source_scan_id),
        (retained.get("source_sha256"), reference.source_sha256),
        (details.get("routed_evidence_sha256"), reference.routed_evidence_sha256),
    )
    if any(actual != expected for actual, expected in expected_pairs):
        raise QuillanAcademicResultArtifactIntegrityError(
            "Manifest evidence provenance disagrees with the exact native selected evidence."
        )
    logical_page = details.get("logical_page")
    if logical_page != page_number:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Selected evidence logical page disagrees with its submission page."
        )
    return evidence, page_number


def _artifact_path(
    root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
    reference: EvidenceReference,
    evidence: Mapping[str, object],
    page_number: int,
) -> tuple[Path, str]:
    relative = _workspace_relative_posix(
        evidence.get("routed_evidence_path"), "routed_evidence_path"
    )
    path = root.joinpath(*PurePosixPath(relative).parts)
    work_ref = quillan_work_ref(manifest.work.class_id, manifest.work.work_id)
    paths = quillan_work_paths(
        root, manifest.work.class_id, manifest.work.work_id
    )
    try:
        path.relative_to(paths.work_root)
    except ValueError as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized routed evidence does not remain inside the exact Quillan work root."
        ) from error
    try:
        canonical = routed_evidence_path(
            root,
            work_ref,
            reference.issuance_id,
            student_id,
            page_number,
            reference.observation_id,
            path.suffix,
        )
    except (QuillanWorkPathError, TypeError, ValueError) as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized routed evidence path cannot be derived canonically."
        ) from error
    if path != canonical:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized routed evidence path is not the exact canonical Quillan "
            "selected-evidence path."
        )
    return path, relative


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    raise QuillanAcademicResultArtifactIntegrityError(
        "Authorized routed evidence has an unsupported media type."
    )


def _read_student_work(
    workspace_root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
) -> tuple[AuthorizedAcademicResultArtifact, ...]:
    student = lookup_academic_result_student(manifest, student_id)
    provenance = student.submission.digital_provenance
    if student.submission.entry_method != "pds2_response_pages" or provenance is None:
        raise QuillanAcademicResultArtifactUnavailableError(
            "Requested student work has no software-readable Quillan artifact."
        )
    if not provenance.evidence_references:
        raise QuillanAcademicResultArtifactUnavailableError(
            "Requested student work has no represented selected evidence artifact."
        )
    native = _load_bound_submission(workspace_root, manifest, student_id)
    results: list[AuthorizedAcademicResultArtifact] = []
    for reference in provenance.evidence_references:
        evidence, page_number = _native_selected_evidence(native, reference)
        artifact_path, relative = _artifact_path(
            workspace_root,
            manifest,
            student_id,
            reference,
            evidence,
            page_number,
        )
        data = _read_regular_file(
            artifact_path,
            workspace_root=workspace_root,
            missing_message="Authorized selected student-work artifact is unavailable.",
        )
        digest = hashlib.sha256(data).hexdigest()
        if digest != reference.routed_evidence_sha256:
            raise QuillanAcademicResultArtifactIntegrityError(
                "Authorized routed-evidence bytes disagree with manifest provenance."
            )
        results.append(
            AuthorizedAcademicResultArtifact(
                artifact_kind="student_work",
                work=manifest.work,
                record_set_revision=manifest.record_set.revision,
                student_id=student_id,
                relative_path=relative,
                media_type=_media_type(artifact_path),
                sha256=digest,
                byte_size=len(data),
                data=data,
                evidence_reference=reference,
            )
        )
    return tuple(results)


def _feedback_target(
    workspace_root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
    artifact_kind: AcademicResultArtifactKind,
) -> tuple[Path, str, str]:
    work_ref = quillan_work_ref(manifest.work.class_id, manifest.work.work_id)
    if artifact_kind == "feedback_pdf":
        path = feedback_pdf_path(workspace_root, work_ref, student_id)
        return path, "feedback_pdf", "application/pdf"
    if artifact_kind == "feedback_markdown":
        path = feedback_markdown_path(workspace_root, work_ref, student_id)
        return path, "feedback_markdown", "text/markdown; charset=utf-8"
    raise QuillanAcademicResultArtifactValidationError(
        "Feedback artifact kind is invalid."
    )


def _metadata_text(
    metadata: Mapping[str, object],
    field: str,
) -> str:
    value = metadata.get(field)
    if not isinstance(value, str) or not value:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Feedback export metadata is invalid."
        )
    return value


def _read_feedback_artifact(
    workspace_root: Path,
    manifest: AcademicResultManifest,
    student_id: str,
    artifact_kind: AcademicResultArtifactKind,
) -> tuple[AuthorizedAcademicResultArtifact, ...]:
    review = _load_bound_review(workspace_root, manifest, student_id)
    exports = _as_mapping(review.get("exports"), "review.exports")
    path, field, media_type = _feedback_target(
        workspace_root, manifest, student_id, artifact_kind
    )
    raw_metadata = exports.get(field)
    if raw_metadata is None:
        raise QuillanAcademicResultArtifactUnavailableError(
            "Requested authorized feedback artifact has no exact export metadata."
        )
    metadata = _as_mapping(raw_metadata, f"review.exports.{field}")
    actual_relative = _workspace_relative_posix(
        metadata.get("path"), f"review.exports.{field}.path"
    )
    expected_relative = path.relative_to(workspace_root).as_posix()
    if actual_relative != expected_relative:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Feedback export metadata path is not the exact canonical Quillan path."
        )
    generated_at = _metadata_text(metadata, "generated_at")
    source_review_updated_at = _metadata_text(
        metadata, "source_review_updated_at"
    )
    review_updated_at = review.get("updated_at")
    if (
        not isinstance(review_updated_at, str)
        or source_review_updated_at != review_updated_at
    ):
        raise QuillanAcademicResultArtifactIntegrityError(
            "Feedback export metadata does not describe the exact manifest-bound review state."
        )
    data = _read_regular_file(
        path,
        workspace_root=workspace_root,
        missing_message="Authorized feedback artifact is unavailable.",
    )
    digest = hashlib.sha256(data).hexdigest()
    return (
        AuthorizedAcademicResultArtifact(
            artifact_kind=artifact_kind,
            work=manifest.work,
            record_set_revision=manifest.record_set.revision,
            student_id=student_id,
            relative_path=expected_relative,
            media_type=media_type,
            sha256=digest,
            byte_size=len(data),
            data=data,
            generated_at=generated_at,
            source_review_updated_at=source_review_updated_at,
        ),
    )


def read_authorized_academic_result_artifacts(
    workspace_root: str | Path,
    manifest: AcademicResultManifest,
    student_id: str,
    artifact_kind: AcademicResultArtifactKind,
    *,
    purpose: str,
    authorization_gate: AcademicResultArtifactAuthorizationGate,
) -> tuple[AuthorizedAcademicResultArtifact, ...]:
    """Return exact producer artifacts only after an external authorization decision."""
    try:
        checked = validate_academic_result_manifest(manifest)
        student = lookup_academic_result_student(checked, student_id)
    except QuillanAcademicResultReaderError as error:
        raise QuillanAcademicResultArtifactValidationError(
            "Artifact manifest or student request is invalid."
        ) from error
    kind = _artifact_kind(artifact_kind)
    bounded_purpose = _purpose(purpose)
    request = AcademicResultArtifactAuthorizationRequest(
        work=checked.work,
        record_set_id=checked.record_set.record_set_id,
        record_set_revision=checked.record_set.revision,
        student_id=student.student_id,
        artifact_kind=kind,
        purpose=bounded_purpose,
    )
    _authorize(authorization_gate, request)

    try:
        root = canonical_workspace_root(workspace_root)
    except QuillanRecordContextError as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized artifact workspace is invalid."
        ) from error
    except OSError as error:
        raise QuillanAcademicResultArtifactReadError(
            "Authorized artifact workspace could not be inspected."
        ) from error
    try:
        if kind == "student_work":
            return _read_student_work(root, checked, student.student_id)
        return _read_feedback_artifact(root, checked, student.student_id, kind)
    except (QuillanWorkPathError, ValueError) as error:
        raise QuillanAcademicResultArtifactIntegrityError(
            "Authorized Quillan artifact path is invalid."
        ) from error


__all__ = (
    "AcademicResultArtifactAuthorizationDecision",
    "AcademicResultArtifactAuthorizationGate",
    "AcademicResultArtifactAuthorizationRequest",
    "AcademicResultArtifactKind",
    "ArtifactAuthorizationStatus",
    "AuthorizedAcademicResultArtifact",
    "QuillanAcademicResultArtifactAuthorizationError",
    "QuillanAcademicResultArtifactError",
    "QuillanAcademicResultArtifactIntegrityError",
    "QuillanAcademicResultArtifactReadError",
    "QuillanAcademicResultArtifactUnavailableError",
    "QuillanAcademicResultArtifactValidationError",
    "read_authorized_academic_result_artifacts",
)

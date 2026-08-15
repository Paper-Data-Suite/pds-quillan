from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

import quillan.academic_result_artifacts as artifacts_module
from quillan._path_safety import is_link_like as shared_is_link_like
from quillan.academic_result_artifacts import (
    AcademicResultArtifactAuthorizationDecision,
    AcademicResultArtifactAuthorizationRequest,
    AuthorizedAcademicResultArtifact,
    QuillanAcademicResultArtifactAuthorizationError,
    QuillanAcademicResultArtifactIntegrityError,
    QuillanAcademicResultArtifactUnavailableError,
    QuillanAcademicResultArtifactValidationError,
    read_authorized_academic_result_artifacts,
)
from quillan.academic_result_manifest import (
    AcademicResultManifest,
    StudentSourceSnapshot,
)
from quillan.academic_result_manifest_generation import (
    build_academic_result_manifest,
    load_academic_result_manifest_generation_context,
)
from quillan.work_paths import quillan_work_ref
from tests.test_academic_result_manifest_generation import _prepare_pds2_pair

EXPECTED_PUBLIC = {
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
}


class Gate:
    def __init__(self, status: str) -> None:
        self.status = status
        self.requests: list[AcademicResultArtifactAuthorizationRequest] = []

    def authorize(
        self, request: AcademicResultArtifactAuthorizationRequest
    ) -> AcademicResultArtifactAuthorizationDecision:
        self.requests.append(request)
        return AcademicResultArtifactAuthorizationDecision(
            cast(object, self.status)  # type: ignore[arg-type]
        )


class RaisingGate:
    def authorize(
        self, request: AcademicResultArtifactAuthorizationRequest
    ) -> AcademicResultArtifactAuthorizationDecision:
        del request
        raise RuntimeError("private authorization backend detail")


def _manifest_and_paths(
    tmp_path: Path,
) -> tuple[AcademicResultManifest, str, str, str, Path, Path]:
    class_id, assignment_id, student_id, retained, routed = _prepare_pds2_pair(
        tmp_path
    )
    context = load_academic_result_manifest_generation_context(
        tmp_path, quillan_work_ref(class_id, assignment_id)
    )
    manifest = build_academic_result_manifest(
        context,
        record_set_revision=7,
        generated_at=datetime(2026, 8, 14, 20, 0, tzinfo=timezone.utc),
    )
    return manifest, class_id, assignment_id, student_id, retained, routed


def _submission_path(
    tmp_path: Path, class_id: str, assignment_id: str, student_id: str
) -> Path:
    return (
        tmp_path
        / "classes"
        / class_id
        / "modules"
        / "quillan"
        / "work"
        / assignment_id
        / "submissions"
        / student_id
        / "submission.json"
    )


def _manifest_with_current_submission_digest(
    manifest: AcademicResultManifest,
    submission_path: Path,
) -> AcademicResultManifest:
    digest = hashlib.sha256(submission_path.read_bytes()).hexdigest()
    student = manifest.students[0]
    source = replace(student.source_snapshot.submission, sha256=digest)
    sources = StudentSourceSnapshot(source, student.source_snapshot.review)
    replaced_student = replace(student, source_snapshot=sources)
    return replace(manifest, students=(replaced_student,))


def test_artifact_module_exports_exact_initial_surface() -> None:
    assert set(artifacts_module.__all__) == EXPECTED_PUBLIC


@pytest.mark.parametrize("status", ["denied", "unresolved"])
def test_denied_or_unresolved_authorization_precedes_any_workspace_access(
    tmp_path: Path,
    status: str,
) -> None:
    manifest, _, _, student_id, _, _ = _manifest_and_paths(tmp_path)
    gate = Gate(status)
    missing_workspace = tmp_path / "does-not-exist"
    with pytest.raises(
        QuillanAcademicResultArtifactAuthorizationError,
        match="not authorized",
    ):
        read_authorized_academic_result_artifacts(
            missing_workspace,
            manifest,
            student_id,
            "student_work",
            purpose="portfolio candidate evaluation",
            authorization_gate=gate,
        )
    assert len(gate.requests) == 1
    request = gate.requests[0]
    assert request.work is manifest.work
    assert request.record_set_id == manifest.record_set.record_set_id
    assert request.record_set_revision == 7
    assert request.student_id == student_id
    assert request.artifact_kind == "student_work"


def test_authorization_backend_exception_is_bounded() -> None:
    fixture = Path(
        "tests/fixtures/publication/quillan_academic_result_manifest_v1.json"
    ).read_bytes()
    from quillan.academic_result_reader import read_academic_result_manifest

    manifest = read_academic_result_manifest(fixture)
    with pytest.raises(
        QuillanAcademicResultArtifactAuthorizationError
    ) as caught:
        read_authorized_academic_result_artifacts(
            Path("definitely-missing"),
            manifest,
            "student_001",
            "student_work",
            purpose="consumer read",
            authorization_gate=RaisingGate(),
        )
    assert "private authorization backend detail" not in str(caught.value)


@pytest.mark.parametrize("purpose", ["", "   ", "\x00", "x" * 501])
def test_invalid_purpose_fails_before_authorization(
    tmp_path: Path, purpose: str
) -> None:
    manifest, _, _, student_id, _, _ = _manifest_and_paths(tmp_path)
    gate = Gate("allowed")
    with pytest.raises(QuillanAcademicResultArtifactValidationError):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "student_work",
            purpose=purpose,
            authorization_gate=gate,
        )
    assert gate.requests == []


def test_invalid_artifact_kind_fails_before_authorization(tmp_path: Path) -> None:
    manifest, _, _, student_id, _, _ = _manifest_and_paths(tmp_path)
    gate = Gate("allowed")
    with pytest.raises(QuillanAcademicResultArtifactValidationError):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "arbitrary_path",  # type: ignore[arg-type]
            purpose="consumer read",
            authorization_gate=gate,
        )
    assert gate.requests == []


def test_authorized_selected_pds2_student_work_returns_exact_routed_bytes(
    tmp_path: Path,
) -> None:
    manifest, _, _, student_id, retained, routed = _manifest_and_paths(tmp_path)
    gate = Gate("allowed")

    result = read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        student_id,
        "student_work",
        purpose="authorized source projection",
        authorization_gate=gate,
    )

    assert len(result) == 1
    artifact = result[0]
    assert isinstance(artifact, AuthorizedAcademicResultArtifact)
    assert artifact.artifact_kind == "student_work"
    assert artifact.work is manifest.work
    assert artifact.record_set_revision == 7
    assert artifact.student_id == student_id
    assert artifact.data == routed.read_bytes()
    assert artifact.relative_path == routed.relative_to(tmp_path).as_posix()
    assert artifact.relative_path != retained.relative_to(tmp_path).as_posix()
    assert artifact.byte_size == len(artifact.data)
    assert artifact.sha256 == hashlib.sha256(artifact.data).hexdigest()
    assert artifact.evidence_reference is (
        manifest.students[0].submission.digital_provenance.evidence_references[0]  # type: ignore[union-attr]
    )
    assert not Path(artifact.relative_path).is_absolute()
    assert str(retained) not in artifact.relative_path


def test_plain_paper_student_work_is_unavailable_after_authorization() -> None:
    from quillan.academic_result_reader import read_academic_result_manifest

    raw = Path(
        "tests/fixtures/publication/quillan_academic_result_manifest_v1.json"
    ).read_bytes()
    manifest = read_academic_result_manifest(raw)
    gate = Gate("allowed")
    with pytest.raises(
        QuillanAcademicResultArtifactUnavailableError,
        match="software-readable",
    ):
        read_authorized_academic_result_artifacts(
            Path("."),
            manifest,
            "student_002",
            "student_work",
            purpose="authorized source projection",
            authorization_gate=gate,
        )
    assert len(gate.requests) == 1


def test_changed_submission_bytes_fail_manifest_bound_integrity(
    tmp_path: Path,
) -> None:
    manifest, class_id, assignment_id, student_id, _, _ = _manifest_and_paths(
        tmp_path
    )
    submission = _submission_path(tmp_path, class_id, assignment_id, student_id)
    submission.write_bytes(submission.read_bytes() + b"\n")
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="source bytes have changed",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_another_students_routed_artifact_cannot_resolve_even_with_matching_bytes(
    tmp_path: Path,
) -> None:
    manifest, class_id, assignment_id, student_id, _, routed = _manifest_and_paths(
        tmp_path
    )
    other_student_path = routed.with_name(
        routed.name.replace(f"response_{student_id}_", "response_99999_", 1)
    )
    assert other_student_path != routed
    other_student_path.write_bytes(routed.read_bytes())

    submission = _submission_path(tmp_path, class_id, assignment_id, student_id)
    data = json.loads(submission.read_text(encoding="utf-8"))
    data["pages"][0]["evidence"][0]["routed_evidence_path"] = (
        other_student_path.relative_to(tmp_path).as_posix()
    )
    submission.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered_manifest = _manifest_with_current_submission_digest(manifest, submission)

    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="exact canonical Quillan selected-evidence path",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered_manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_changed_routed_bytes_fail_manifest_provenance(
    tmp_path: Path,
) -> None:
    manifest, _, _, student_id, _, routed = _manifest_and_paths(tmp_path)
    routed.write_bytes(routed.read_bytes() + b"tampered")
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="routed-evidence bytes",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_native_selection_is_independently_rechecked_after_source_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, class_id, assignment_id, student_id, _, _ = _manifest_and_paths(
        tmp_path
    )
    submission = _submission_path(tmp_path, class_id, assignment_id, student_id)
    data = json.loads(submission.read_text(encoding="utf-8"))
    data["pages"][0]["selected_evidence_id"] = None
    submission.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered_manifest = _manifest_with_current_submission_digest(manifest, submission)

    # Prove the artifact resolver owns an independent selected-evidence check even
    # if a future regression in the native schema validator were to admit this state.
    monkeypatch.setattr(
        artifacts_module,
        "validate_submission_manifest",
        lambda _value: None,
    )
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="authoritative selected",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered_manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_native_selected_role_is_independently_rechecked_after_source_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, class_id, assignment_id, student_id, _, _ = _manifest_and_paths(
        tmp_path
    )
    submission = _submission_path(tmp_path, class_id, assignment_id, student_id)
    data = json.loads(submission.read_text(encoding="utf-8"))
    data["pages"][0]["evidence"][0]["evidence_role"] = "candidate"
    submission.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered_manifest = _manifest_with_current_submission_digest(manifest, submission)

    monkeypatch.setattr(
        artifacts_module,
        "validate_submission_manifest",
        lambda _value: None,
    )
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="selected evidence role",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered_manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_native_provenance_identity_is_rechecked_even_with_matching_source_digest(
    tmp_path: Path,
) -> None:
    manifest, class_id, assignment_id, student_id, _, _ = _manifest_and_paths(
        tmp_path
    )
    submission = _submission_path(tmp_path, class_id, assignment_id, student_id)
    data = json.loads(submission.read_text(encoding="utf-8"))
    data["pages"][0]["evidence"][0]["module_details"]["route_id"] = (
        "rt_ffffffffffffffffffffffffffffffff"
    )
    submission.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered_manifest = _manifest_with_current_submission_digest(manifest, submission)
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="provenance disagrees",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered_manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_link_like_routed_artifact_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _, _, student_id, _, routed = _manifest_and_paths(tmp_path)
    def link_only(path: Path) -> bool:
        return path == routed or shared_is_link_like(path)

    monkeypatch.setattr(
        "quillan.academic_result_artifacts.is_link_like",
        link_only,
    )
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="link-like component",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_link_like_parent_component_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _, _, student_id, _, routed = _manifest_and_paths(tmp_path)
    linked_parent = routed.parent

    def parent_link(path: Path) -> bool:
        return path == linked_parent or shared_is_link_like(path)

    monkeypatch.setattr(
        "quillan.academic_result_artifacts.is_link_like",
        parent_link,
    )
    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="link-like component",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            student_id,
            "student_work",
            purpose="authorized source projection",
            authorization_gate=Gate("allowed"),
        )


def test_result_exposes_no_absolute_or_retained_source_path(tmp_path: Path) -> None:
    manifest, _, _, student_id, retained, _ = _manifest_and_paths(tmp_path)
    artifact = read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        student_id,
        "student_work",
        purpose="authorized source projection",
        authorization_gate=Gate("allowed"),
    )[0]
    rendered = repr(artifact)
    assert str(tmp_path) not in rendered
    assert str(retained) not in rendered
    assert "retained_source_path" not in rendered
    assert "source_filename" not in rendered


@pytest.mark.parametrize("artifact_kind", ["feedback_pdf", "feedback_markdown"])
def test_feedback_kinds_require_authorization_before_workspace_access(
    tmp_path: Path,
    artifact_kind: str,
) -> None:
    manifest, _, _, student_id, _, _ = _manifest_and_paths(tmp_path)
    denied = Gate("denied")
    missing_workspace = tmp_path / "missing-workspace"
    with pytest.raises(QuillanAcademicResultArtifactAuthorizationError):
        read_authorized_academic_result_artifacts(
            missing_workspace,
            manifest,
            student_id,
            artifact_kind,  # type: ignore[arg-type]
            purpose="consumer feedback read",
            authorization_gate=denied,
        )
    assert len(denied.requests) == 1


def test_artifact_source_has_no_consumer_or_core_publication_policy_dependency() -> None:
    source = Path("quillan/academic_result_artifacts.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in (
        "import meridian",
        "from meridian",
        "import vitrine",
        "from vitrine",
        "import scoreform",
        "from scoreform",
        "import concord",
        "from concord",
        "academic_catalog",
        "publication_storage",
        "registry_services",
        "query_publication_catalog",
        "grade_item",
        "portfolio_candidate",
        "portfolio_selection",
    ):
        assert forbidden not in lowered

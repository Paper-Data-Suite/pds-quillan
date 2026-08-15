from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from quillan._path_safety import is_link_like as shared_is_link_like
from quillan.academic_result_artifacts import (
    AcademicResultArtifactAuthorizationDecision,
    AcademicResultArtifactAuthorizationRequest,
    AuthorizedAcademicResultArtifact,
    QuillanAcademicResultArtifactIntegrityError,
    QuillanAcademicResultArtifactUnavailableError,
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
from quillan.feedback_export import (
    export_student_feedback,
    export_student_feedback_pdf,
)
from quillan.work_paths import (
    feedback_markdown_path,
    feedback_pdf_path,
    quillan_work_ref,
    review_record_path,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID
from tests.test_academic_result_manifest_generation import _prepare_plain_pair

EXPORT_TIME = "2026-08-14T21:30:00+00:00"


class AllowGate:
    def __init__(self) -> None:
        self.requests: list[AcademicResultArtifactAuthorizationRequest] = []

    def authorize(
        self,
        request: AcademicResultArtifactAuthorizationRequest,
    ) -> AcademicResultArtifactAuthorizationDecision:
        self.requests.append(request)
        return AcademicResultArtifactAuthorizationDecision("allowed")


def _build_current_manifest(tmp_path: Path, revision: int = 9) -> AcademicResultManifest:
    context = load_academic_result_manifest_generation_context(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
    )
    return build_academic_result_manifest(
        context,
        record_set_revision=revision,
        generated_at=datetime(2026, 8, 14, 22, 0, tzinfo=timezone.utc),
    )


def _manifest_with_current_review_digest(
    manifest: AcademicResultManifest,
    review_path: Path,
) -> AcademicResultManifest:
    digest = hashlib.sha256(review_path.read_bytes()).hexdigest()
    student = manifest.students[0]
    review_source = replace(student.source_snapshot.review, sha256=digest)
    sources = StudentSourceSnapshot(
        student.source_snapshot.submission,
        review_source,
    )
    replaced_student = replace(student, source_snapshot=sources)
    return replace(manifest, students=(replaced_student,))


def test_authorized_pdf_feedback_reads_exact_metadata_backed_bytes(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback_pdf(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    gate = AllowGate()

    result = read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        STUDENT_ID,
        "feedback_pdf",
        purpose="authorized feedback display",
        authorization_gate=gate,
    )

    assert len(result) == 1
    artifact = result[0]
    assert isinstance(artifact, AuthorizedAcademicResultArtifact)
    assert artifact.data == exported.feedback_pdf_path.read_bytes()
    assert artifact.media_type == "application/pdf"
    assert artifact.relative_path == exported.feedback_pdf_path.relative_to(
        tmp_path
    ).as_posix()
    assert artifact.sha256 == hashlib.sha256(artifact.data).hexdigest()
    assert artifact.byte_size == len(artifact.data)
    assert artifact.evidence_reference is None
    assert artifact.generated_at == EXPORT_TIME
    assert artifact.source_review_updated_at == EXPORT_TIME
    assert len(gate.requests) == 1


def test_markdown_only_export_persists_metadata_and_resolves_exact_bytes(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    review_path = review_record_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    metadata = review["exports"]["feedback_markdown"]
    assert metadata == {
        "path": exported.feedback_path.relative_to(tmp_path).as_posix(),
        "generated_at": EXPORT_TIME,
        "source_review_updated_at": EXPORT_TIME,
        "module_details": {},
    }
    assert review["exports"]["feedback_pdf"] is None
    assert review["updated_at"] == EXPORT_TIME
    assert review["review_state"] == "exported"

    manifest = _build_current_manifest(tmp_path)
    artifact = read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        STUDENT_ID,
        "feedback_markdown",
        purpose="authorized feedback display",
        authorization_gate=AllowGate(),
    )[0]
    assert artifact.data == exported.feedback_path.read_bytes()
    assert artifact.media_type == "text/markdown; charset=utf-8"
    assert artifact.relative_path == exported.feedback_path.relative_to(
        tmp_path
    ).as_posix()
    assert artifact.generated_at == EXPORT_TIME
    assert artifact.source_review_updated_at == EXPORT_TIME


def test_feedback_format_never_falls_back_to_other_export(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    assert exported.feedback_path.is_file()
    assert not feedback_pdf_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    ).exists()
    manifest = _build_current_manifest(tmp_path)

    with pytest.raises(
        QuillanAcademicResultArtifactUnavailableError,
        match="no exact export metadata",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            STUDENT_ID,
            "feedback_pdf",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_feedback_file_presence_without_export_metadata_is_not_access(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    path = feedback_pdf_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 synthetic")
    manifest = _build_current_manifest(tmp_path)

    with pytest.raises(
        QuillanAcademicResultArtifactUnavailableError,
        match="no exact export metadata",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            STUDENT_ID,
            "feedback_pdf",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_review_change_after_manifest_blocks_feedback_resolution(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    review_path = review_record_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    review_path.write_bytes(review_path.read_bytes() + b"\n")

    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="review source bytes have changed",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            manifest,
            STUDENT_ID,
            "feedback_markdown",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_feedback_metadata_path_must_be_exact_canonical_path(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    review_path = review_record_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["exports"]["feedback_markdown"]["path"] = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
        f"submissions/{STUDENT_ID}/exports/not-feedback.md"
    )
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered = _manifest_with_current_review_digest(manifest, review_path)

    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="exact canonical",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered,
            STUDENT_ID,
            "feedback_markdown",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_feedback_metadata_must_match_exact_review_updated_at(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    review_path = review_record_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["exports"]["feedback_markdown"]["source_review_updated_at"] = (
        "2026-08-14T21:29:59+00:00"
    )
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    altered = _manifest_with_current_review_digest(manifest, review_path)

    with pytest.raises(
        QuillanAcademicResultArtifactIntegrityError,
        match="exact manifest-bound review state",
    ):
        read_authorized_academic_result_artifacts(
            tmp_path,
            altered,
            STUDENT_ID,
            "feedback_markdown",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_link_like_feedback_parent_component_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    linked_parent = exported.feedback_path.parent

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
            STUDENT_ID,
            "feedback_markdown",
            purpose="authorized feedback display",
            authorization_gate=AllowGate(),
        )


def test_feedback_result_does_not_expose_review_body_or_absolute_paths(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    artifact = read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        STUDENT_ID,
        "feedback_markdown",
        purpose="authorized feedback display",
        authorization_gate=AllowGate(),
    )[0]
    rendered = repr(artifact)
    assert str(tmp_path) not in rendered
    assert "private_notes" not in rendered
    assert "review.json" not in rendered
    assert artifact.relative_path == feedback_markdown_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    ).relative_to(tmp_path).as_posix()
    assert artifact.data == exported.feedback_path.read_bytes()


def test_feedback_artifact_reader_does_not_mutate_review_or_artifact(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=EXPORT_TIME,
    )
    manifest = _build_current_manifest(tmp_path)
    review_path = review_record_path(
        tmp_path,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        STUDENT_ID,
    )
    before_review = review_path.read_bytes()
    before_artifact = exported.feedback_path.read_bytes()

    read_authorized_academic_result_artifacts(
        tmp_path,
        manifest,
        STUDENT_ID,
        "feedback_markdown",
        purpose="authorized feedback display",
        authorization_gate=AllowGate(),
    )

    assert review_path.read_bytes() == before_review
    assert exported.feedback_path.read_bytes() == before_artifact

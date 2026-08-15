"""Installed clean-wheel producer acceptance for Quillan academic results."""

from __future__ import annotations

import argparse
import hashlib
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Callable
from typing import Literal, TypeVar

import pds_core
from pds_core.academic_catalog import (
    CatalogPublication,
    PublicationCatalogQuery,
    query_publication_catalog,
    rebuild_academic_catalog,
)
from pds_core.academic_work_registration_storage import (
    list_academic_work_registration_revisions,
    load_academic_work_registration_revision,
    load_current_academic_work_registration,
)
from pds_core.publication_compatibility import (
    discover_publication_producer_profiles,
    evaluate_publication_compatibility,
)
from pds_core.publication_records import validate_publication_record_series
from pds_core.publication_storage import (
    get_current_publication_record,
    list_publication_record_set,
    load_publication_record,
    load_publication_withdrawal,
    verify_publication_manifest,
)
from pds_core.registry_audit import RegistryAuditOptions, audit_academic_registry
from pds_core.registry_paths import (
    academic_work_registration_revision_path,
    publication_record_path,
    publication_withdrawal_path,
)
from pds_core.routing_models import ModuleRecordRef
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name
from pip._vendor.packaging.version import Version

from quillan.academic_result_artifacts import (
    AcademicResultArtifactAuthorizationDecision,
    AcademicResultArtifactAuthorizationRequest,
    QuillanAcademicResultArtifactAuthorizationError,
    QuillanAcademicResultArtifactIntegrityError,
    read_authorized_academic_result_artifacts,
)
from quillan.academic_result_manifest import (
    ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    REVIEW_SOURCE_CONTRACT_VERSION,
    SUBMISSION_SOURCE_CONTRACT_VERSION,
    AcademicResultManifest,
)
from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    generate_academic_result_manifest,
)
from quillan.academic_result_publication import (
    QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
    QUILLAN_PUBLICATION_CAPABILITIES,
    AcademicResultPublicationResult,
    AcademicResultWithdrawalResult,
    QuillanAcademicResultPublicationConflictError,
    QuillanAcademicResultPublicationIntegrityError,
    publish_quillan_academic_results,
    supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.academic_result_reader import (
    QuillanAcademicResultReaderNotFoundError,
    lookup_academic_result_evidence_reference,
    lookup_academic_result_observation,
    lookup_academic_result_overall_rating,
    lookup_academic_result_review_unit,
    lookup_academic_result_source,
    lookup_academic_result_standard_feedback,
    lookup_academic_result_student,
    read_academic_result_manifest,
)
from quillan.academic_work_registration import (
    QUILLAN_ACADEMIC_WORK_KIND,
    QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
    load_current_quillan_academic_work_registration,
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)
from quillan.pds_contract import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_MODULE_ID,
)
from quillan.pds_publication import get_publication_producer_profile
from quillan.publication_revision_policy import (
    QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
)
from quillan.work_paths import quillan_work_paths, quillan_work_ref

CLASS_ID = "synthetic_release_class"
ASSIGNMENT_ID = "synthetic_release_digital"
REVIEWED_STUDENT_ID = "00107"
UNREVIEWED_STUDENT_ID = "00208"
STANDARD_ID = "synthetic:W.RELEASE.1"
PURPOSE = "installed producer acceptance"
WITHDRAWAL_REASON = "synthetic acceptance withdrawal"

ACADEMIC_STATE_PATHS = (
    Path("settings/academic_periods"),
    Path("registry/work"),
    Path("registry/publications"),
    Path("registry/withdrawals"),
    Path("registry/catalog.sqlite"),
    Path("registry/.locks"),
)

STAGES = (
    "installed provenance",
    "native workflow handoff",
    "academic-work registration",
    "manifest revision 1",
    "public reader revision 1",
    "initial publication",
    "publication replay",
    "catalog revision 1",
    "Core verification revision 1",
    "authorized artifacts revision 1",
    "registration independence",
    "native correction",
    "manifest revision 2",
    "supersession",
    "catalog revision 2",
    "Core verification revision 2",
    "authorized artifacts revision 2",
    "historical source drift",
    "withdrawal",
    "final catalog",
    "registry audit",
    "immutability",
)

_T = TypeVar("_T")


class AcceptanceFailure(RuntimeError):
    """Bounded stage failure that never renders private payloads."""

    def __init__(self, stage: str, message: str) -> None:
        if stage not in STAGES:
            raise ValueError("stage must be a known producer-acceptance stage.")
        if not isinstance(message, str) or not message or "\n" in message or "\r" in message:
            raise ValueError("message must be a nonempty single line.")
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.message = message


def _require(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(stage, message)


def _run_stage(stage: str, action: Callable[[], _T]) -> _T:
    print(f"Running: {stage}")
    try:
        value = action()
    except AcceptanceFailure:
        raise
    except Exception as error:
        raise AcceptanceFailure(
            stage, f"production operation failed ({type(error).__name__})."
        ) from error
    print(f"PASSED: {stage}")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if type(value) is not dict:
        raise ValueError("expected a JSON object")
    return value


def _module_origin(name: str) -> Path:
    module = importlib.import_module(name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise ValueError("module has no file origin")
    return Path(raw).resolve()


def _installed_origin(path: Path, repository: Path) -> bool:
    return (
        path.is_relative_to(Path(sys.prefix).resolve())
        and "site-packages" in {part.lower() for part in path.parts}
        and not path.is_relative_to(repository)
    )


def _assert_no_academic_state(workspace: Path, stage: str) -> None:
    created = [path.as_posix() for path in ACADEMIC_STATE_PATHS if (workspace / path).exists()]
    _require(not created, stage, "academic registry state existed before explicit registration.")


def _installed_provenance(
    workspace: Path, repository: Path, *, version: str, core_version: str
) -> None:
    _require("PYTHONPATH" not in os.environ, "installed provenance", "PYTHONPATH must be cleared.")
    _require(metadata.version("quillan") == version, "installed provenance", "Quillan version disagrees.")
    installed_core = metadata.version("pds-core")
    _require(installed_core == core_version == "0.6.0", "installed provenance", "Core version disagrees.")
    _require(pds_core.__version__ == installed_core, "installed provenance", "Core module version disagrees.")
    requirements = tuple(Requirement(value) for value in (metadata.requires("quillan") or ()))
    core_requirements = tuple(
        value for value in requirements if canonicalize_name(value.name) == "pds-core"
    )
    _require(
        len(core_requirements) == 1 and Version(installed_core) in core_requirements[0].specifier,
        "installed provenance",
        "Quillan dependency metadata rejects Core 0.6.0.",
    )
    required_modules = (
        "quillan",
        "quillan.academic_work_registration",
        "quillan.academic_result_manifest_generation",
        "quillan.academic_result_publication",
        "quillan.academic_result_reader",
        "quillan.academic_result_artifacts",
        "quillan.pds_publication",
        "pds_core",
        "pds_core.academic_work_registration_storage",
        "pds_core.publication_storage",
        "pds_core.publication_compatibility",
        "pds_core.academic_catalog",
        "pds_core.registry_audit",
    )
    for name in required_modules:
        _require(
            _installed_origin(_module_origin(name), repository),
            "installed provenance",
            f"{name} did not import from isolated site-packages.",
        )
    entries = tuple(
        entry
        for entry in metadata.distribution("quillan").entry_points
        if entry.group == "paper_data_suite.publication_producers"
    )
    _require(
        [(entry.name, entry.value) for entry in entries]
        == [("quillan", "quillan.pds_publication:get_publication_producer_profile")],
        "installed provenance",
        "publication-producer entry point disagrees.",
    )
    profile = get_publication_producer_profile()
    discovered = tuple(
        item for item in discover_publication_producer_profiles() if item.module_id == "quillan"
    )
    _require(discovered == (profile,), "installed provenance", "Core profile discovery disagrees.")
    sibling_roots = {"meridian", "vitrine", "scoreform", "concord", "portia"}
    _require(
        not {name.split(".", 1)[0] for name in sys.modules}.intersection(sibling_roots),
        "installed provenance",
        "a sibling producer or consumer was imported.",
    )
    _assert_no_academic_state(workspace, "installed provenance")


def _native_handoff(workspace: Path) -> tuple[Path, Path, Path]:
    paths = quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID)
    assignment = paths.assignment_path
    submission = paths.submissions_dir / REVIEWED_STUDENT_ID / "submission.json"
    review = paths.submissions_dir / REVIEWED_STUDENT_ID / "review.json"
    unreviewed = paths.submissions_dir / UNREVIEWED_STUDENT_ID / "submission.json"
    _require(
        all(path.is_file() for path in (assignment, submission, review, unreviewed)),
        "native workflow handoff",
        "ordinary installed workflow did not provide the expected native records.",
    )
    review_value = _load_json(review)
    private_notes = review_value.get("private_notes")
    _require(
        review_value.get("review_state") == "exported"
        and isinstance(private_notes, list)
        and len(private_notes) == 1,
        "native workflow handoff",
        "reviewed synthetic work is incomplete.",
    )
    exports = review_value.get("exports")
    _require(
        isinstance(exports, dict)
        and isinstance(exports.get("feedback_pdf"), dict)
        and isinstance(exports.get("feedback_markdown"), dict),
        "native workflow handoff",
        "both feedback exports are required.",
    )
    _assert_no_academic_state(workspace, "native workflow handoff")
    return assignment, submission, review


def _register(workspace: Path) -> tuple[object, bytes]:
    first = register_quillan_academic_work(
        workspace, CLASS_ID, ASSIGNMENT_ID, academic_intent="summative", lifecycle="active"
    )
    replay = register_quillan_academic_work(
        workspace, CLASS_ID, ASSIGNMENT_ID, academic_intent="summative", lifecycle="active"
    )
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    registration = first.registration
    expected_source = ModuleRecordRef(
        module_id="quillan",
        record_kind=QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
        record_id=ASSIGNMENT_ID,
        contract_version=QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    )
    _require(
        first.disposition == "created"
        and registration.registration_revision == 1
        and replay.disposition == "existing"
        and replay.registration == registration,
        "academic-work registration",
        "registration create/replay disagrees.",
    )
    _require(
        registration.work == work
        and registration.producer_contract_version == QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION
        and registration.work_kind == QUILLAN_ACADEMIC_WORK_KIND
        and registration.source_records == (expected_source,)
        and load_current_quillan_academic_work_registration(workspace, CLASS_ID, ASSIGNMENT_ID)
        == registration
        and load_current_academic_work_registration(workspace, work) == registration,
        "academic-work registration",
        "canonical registration contract disagrees.",
    )
    path = academic_work_registration_revision_path(workspace, work, 1)
    return registration, path.read_bytes()


def _manifest_one(
    workspace: Path, assignment: Path, submission: Path, review: Path
) -> AcademicResultManifestGenerationResult:
    result = generate_academic_result_manifest(workspace, CLASS_ID, ASSIGNMENT_ID)
    manifest = result.manifest
    _require(
        result.disposition == "create_initial"
        and result.reason == "initial_publication"
        and result.revision == 1
        and manifest.record_set.record_set_id == QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
        and manifest.contract_version == ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
        and manifest.producer_module_id == QUILLAN_MODULE_ID
        and result.content == result.path.read_bytes()
        and result.sha256 == _sha256(result.content),
        "manifest revision 1",
        "initial immutable manifest identity or digest disagrees.",
    )
    _require(
        len(manifest.students) == 1
        and manifest.students[0].student_id == REVIEWED_STUDENT_ID
        and manifest.source_snapshot.sha256 == _sha256(assignment.read_bytes())
        and manifest.students[0].source_snapshot.submission.sha256 == _sha256(submission.read_bytes())
        and manifest.students[0].source_snapshot.review.sha256 == _sha256(review.read_bytes()),
        "manifest revision 1",
        "native representation or source snapshots disagree.",
    )
    return result


def _verify_reader(content: bytes, *, rating: int, stage: str) -> AcademicResultManifest:
    manifest = read_academic_result_manifest(content)
    student = lookup_academic_result_student(manifest, REVIEWED_STUDENT_ID)
    assignment_source = lookup_academic_result_source(manifest, "assignment")
    submission_source = lookup_academic_result_source(
        manifest, "submission", student_id=REVIEWED_STUDENT_ID
    )
    review_source = lookup_academic_result_source(
        manifest, "review", student_id=REVIEWED_STUDENT_ID
    )
    unit = student.review.review_units[0]
    observation = unit.standard_observations[0]
    feedback = lookup_academic_result_standard_feedback(
        manifest, REVIEWED_STUDENT_ID, STANDARD_ID
    )
    provenance = student.submission.digital_provenance
    if provenance is None or not provenance.evidence_references:
        raise AcceptanceFailure(stage, "selected evidence is absent.")
    reference = provenance.evidence_references[0]
    _require(
        lookup_academic_result_review_unit(manifest, REVIEWED_STUDENT_ID, unit.unit_id) == unit
        and lookup_academic_result_observation(
            manifest, REVIEWED_STUDENT_ID, observation.observation_id
        )
        == observation
        and lookup_academic_result_overall_rating(
            manifest, REVIEWED_STUDENT_ID, STANDARD_ID
        ).rating
        == rating
        and lookup_academic_result_evidence_reference(
            manifest, REVIEWED_STUDENT_ID, reference.evidence_id
        )
        == reference
        and assignment_source.relative_path == "assignment.json"
        and assignment_source.contract_version == ASSIGNMENT_SOURCE_CONTRACT_VERSION
        and submission_source.relative_path
        == f"submissions/{REVIEWED_STUDENT_ID}/submission.json"
        and submission_source.contract_version == SUBMISSION_SOURCE_CONTRACT_VERSION
        and review_source.relative_path
        == f"submissions/{REVIEWED_STUDENT_ID}/review.json"
        and review_source.contract_version == REVIEW_SOURCE_CONTRACT_VERSION
        and len(feedback.comments) == 1
        and all(
            comment.text.disposition in {"included", "withheld"}
            for comment in feedback.comments
        )
        and b'"private_notes"' not in content
        and b'"retained_source_path"' not in content
        and b'"routed_evidence_path"' not in content,
        stage,
        "public reader semantics or privacy boundary disagree.",
    )
    try:
        lookup_academic_result_student(manifest, UNREVIEWED_STUDENT_ID)
    except QuillanAcademicResultReaderNotFoundError:
        pass
    else:
        raise AcceptanceFailure(stage, "unreviewed student was fabricated into the result.")
    return manifest


def _verify_publication(
    result: AcademicResultPublicationResult,
    generated: AcademicResultManifestGenerationResult,
    *, revision: int,
    registration_revision: int,
    supersedes: str | None,
    stage: str,
) -> None:
    publication = result.publication
    _require(
        publication.work == quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
        and publication.publication_kind == QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND
        and publication.record_set_id == QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
        and publication.record_set_revision == revision
        and publication.manifest_contract_version == ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
        and publication.capabilities == QUILLAN_PUBLICATION_CAPABILITIES
        and publication.source_record is None
        and publication.manifest_digest_algorithm == "sha256"
        and publication.manifest_digest == generated.sha256
        and publication.academic_work_registration_revision == registration_revision
        and publication.supersedes_publication_id == supersedes,
        stage,
        "Core Publication Record envelope disagrees.",
    )


def _series_query(
    state: Literal["current", "series_heads", "historical", "withdrawn", "all"]
) -> PublicationCatalogQuery:
    return PublicationCatalogQuery(
        class_id=CLASS_ID,
        module_id=QUILLAN_MODULE_ID,
        work_id=ASSIGNMENT_ID,
        publication_kind=QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
        required_capabilities=QUILLAN_PUBLICATION_CAPABILITIES,
        manifest_contract_version=ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
        record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        state=state,
    )


def _query(
    workspace: Path,
    state: Literal["current", "series_heads", "historical", "withdrawn", "all"],
) -> tuple[CatalogPublication, ...]:
    return query_publication_catalog(workspace, _series_query(state))


def _catalog_one(workspace: Path, publication_id: str) -> None:
    rebuild_academic_catalog(workspace)
    rows = _query(workspace, "all")
    _require(
        len(rows) == 1
        and rows[0].publication_id == publication_id
        and rows[0].is_series_head
        and not rows[0].is_withdrawn
        and rows[0].is_current_selectable
        and load_publication_record(workspace, publication_id).publication_id == publication_id,
        "catalog revision 1",
        "independent catalog/canonical discovery disagrees.",
    )


def _core_verified(
    workspace: Path,
    publication_id: str,
    generated: AcademicResultManifestGenerationResult,
    *,
    stage: str,
) -> bytes:
    publication = load_publication_record(workspace, publication_id)
    registration_revision = publication.academic_work_registration_revision
    if registration_revision is None:
        raise AcceptanceFailure(
            stage, "academic-result publication omitted its registration revision."
        )
    registration = load_academic_work_registration_revision(
        workspace, publication.work, registration_revision
    )
    series = list_publication_record_set(
        workspace, publication.work, publication.publication_kind, publication.record_set_id
    )
    validate_publication_record_series(series)
    profile = get_publication_producer_profile()
    compatibility = evaluate_publication_compatibility(publication, profile, registration)
    _require(
        compatibility.compatible
        and compatibility.codes == ()
        and load_publication_withdrawal(workspace, publication_id) is None,
        stage,
        "canonical compatibility or withdrawal state disagrees.",
    )
    manifest_read_authorized = (
        publication.work == quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
        and publication.record_set_id == QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
        and publication.record_set_revision == generated.revision
        and REVIEWED_STUDENT_ID == "00107"
        and PURPOSE == "installed producer acceptance"
    )
    _require(
        manifest_read_authorized,
        stage,
        "acceptance-owned student-level manifest authorization was not allowed.",
    )
    path = verify_publication_manifest(workspace, publication)
    content = path.read_bytes()
    _require(
        path.resolve(strict=True) == generated.path.resolve(strict=True)
        and content == generated.content
        and _sha256(content) == publication.manifest_digest,
        stage,
        "Core manifest path or digest verification disagrees.",
    )
    return content


class _ExactGate:
    def __init__(self, manifest: AcademicResultManifest, *, allow: bool = True) -> None:
        self.manifest = manifest
        self.allow = allow
        self.requests: list[AcademicResultArtifactAuthorizationRequest] = []

    def authorize(
        self, request: AcademicResultArtifactAuthorizationRequest
    ) -> AcademicResultArtifactAuthorizationDecision:
        self.requests.append(request)
        exact = (
            request.work == self.manifest.work
            and request.record_set_id == self.manifest.record_set.record_set_id
            and request.record_set_revision == self.manifest.record_set.revision
            and request.student_id == REVIEWED_STUDENT_ID
            and request.artifact_kind in {"student_work", "feedback_pdf", "feedback_markdown"}
            and request.purpose == PURPOSE
        )
        return AcademicResultArtifactAuthorizationDecision(
            "allowed" if self.allow and exact else "denied"
        )


def _artifacts(
    workspace: Path, manifest: AcademicResultManifest, *, stage: str
) -> tuple[tuple[object, ...], tuple[object, ...], tuple[object, ...]]:
    gate = _ExactGate(manifest)
    work = read_authorized_academic_result_artifacts(
        workspace,
        manifest,
        REVIEWED_STUDENT_ID,
        "student_work",
        purpose=PURPOSE,
        authorization_gate=gate,
    )
    pdf = read_authorized_academic_result_artifacts(
        workspace,
        manifest,
        REVIEWED_STUDENT_ID,
        "feedback_pdf",
        purpose=PURPOSE,
        authorization_gate=gate,
    )
    markdown = read_authorized_academic_result_artifacts(
        workspace,
        manifest,
        REVIEWED_STUDENT_ID,
        "feedback_markdown",
        purpose=PURPOSE,
        authorization_gate=gate,
    )
    student = lookup_academic_result_student(manifest, REVIEWED_STUDENT_ID)
    provenance = student.submission.digital_provenance
    references = () if provenance is None else provenance.evidence_references
    current_review = _load_json(
        quillan_work_paths(workspace, CLASS_ID, ASSIGNMENT_ID).submissions_dir
        / REVIEWED_STUDENT_ID
        / "review.json"
    )
    review_updated_at = current_review.get("updated_at")
    _require(
        len(references) == 2
        and len(work) == len(references)
        and tuple(getattr(item, "evidence_reference") for item in work) == references
        and all(
            getattr(item, "artifact_kind") == "student_work"
            and getattr(item, "media_type") == "image/png"
            and getattr(item, "sha256")
            == getattr(item, "evidence_reference").routed_evidence_sha256
            for item in work
        )
        and len(pdf) == len(markdown) == 1
        and getattr(pdf[0], "artifact_kind") == "feedback_pdf"
        and getattr(pdf[0], "media_type") == "application/pdf"
        and getattr(markdown[0], "artifact_kind") == "feedback_markdown"
        and getattr(markdown[0], "media_type") == "text/markdown; charset=utf-8"
        and getattr(pdf[0], "source_review_updated_at") == review_updated_at
        and getattr(markdown[0], "source_review_updated_at") == review_updated_at
        and all(
            getattr(item, "byte_size") == len(getattr(item, "data"))
            and getattr(item, "sha256") == _sha256(getattr(item, "data"))
            and not Path(getattr(item, "relative_path")).is_absolute()
            for item in (*work, *pdf, *markdown)
        )
        and len(gate.requests) == 3,
        stage,
        "authorized exact artifact results disagree.",
    )
    denied = _ExactGate(manifest, allow=False)
    try:
        read_authorized_academic_result_artifacts(
            workspace,
            manifest,
            REVIEWED_STUDENT_ID,
            "feedback_markdown",
            purpose=PURPOSE,
            authorization_gate=denied,
        )
    except QuillanAcademicResultArtifactAuthorizationError:
        pass
    else:
        raise AcceptanceFailure(stage, "denied artifact request was not rejected.")
    return work, pdf, markdown


def _registration_independence(
    workspace: Path,
    generated: AcademicResultManifestGenerationResult,
    published: AcademicResultPublicationResult,
) -> tuple[object, bytes]:
    updated = update_quillan_academic_work_registration(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="closed",
        expected_current_revision=1,
    )
    replay_manifest = generate_academic_result_manifest(workspace, CLASS_ID, ASSIGNMENT_ID)
    replay_publication = publish_quillan_academic_results(
        workspace, CLASS_ID, ASSIGNMENT_ID, manifest_revision=1
    )
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    _require(
        updated.disposition == "updated"
        and updated.registration.registration_revision == 2
        and list_academic_work_registration_revisions(workspace, work) == (1, 2)
        and replay_manifest.disposition == "reuse_existing"
        and replay_manifest.reason == "exact_replay"
        and replay_manifest.content == generated.content
        and replay_manifest.manifest.generated_at == generated.manifest.generated_at
        and replay_publication.disposition == "existing"
        and replay_publication.publication == published.publication
        and replay_publication.publication.academic_work_registration_revision == 1,
        "registration independence",
        "registration-only update altered manifest/publication history.",
    )
    path = academic_work_registration_revision_path(workspace, work, 2)
    return updated.registration, path.read_bytes()


def _cli(arguments: list[str], workspace: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PDS_WORKSPACE_ROOT"] = str(workspace)
    result = subprocess.run(
        [sys.executable, "-c", "from quillan.cli import main; raise SystemExit(main())", *arguments],
        cwd=workspace.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("installed Quillan command failed")


def _native_correction(workspace: Path, review_path: Path) -> bytes:
    identity = [CLASS_ID, ASSIGNMENT_ID, REVIEWED_STUDENT_ID]
    _cli(
        [
            "ratings",
            "set",
            *identity,
            "--standard-id",
            STANDARD_ID,
            "--rating",
            "1",
            "--rationale",
            "Synthetic corrected overall rating.",
            "--include-in-feedback",
            "true",
        ],
        workspace,
    )
    _cli(
        ["export-feedback", *identity, "--format", "both", "--overwrite"],
        workspace,
    )
    corrected = review_path.read_bytes()
    value = _load_json(review_path)
    ratings = value.get("overall_standard_ratings")
    _require(
        isinstance(ratings, list)
        and len(ratings) == 1
        and isinstance(ratings[0], dict)
        and ratings[0].get("rating") == 1
        and value.get("review_state") == "exported",
        "native correction",
        "supported review correction/export did not persist native rating 1.",
    )
    return corrected


def _manifest_two(
    workspace: Path,
    revision_one: AcademicResultManifestGenerationResult,
    corrected_review: bytes,
) -> AcademicResultManifestGenerationResult:
    result = generate_academic_result_manifest(workspace, CLASS_ID, ASSIGNMENT_ID)
    student = result.manifest.students[0]
    _require(
        result.disposition == "create_successor"
        and result.reason == "native_source_changed"
        and result.revision == 2
        and result.sha256 == _sha256(result.content)
        and result.sha256 != revision_one.sha256
        and revision_one.path.read_bytes() == revision_one.content
        and student.source_snapshot.review.sha256 == _sha256(corrected_review),
        "manifest revision 2",
        "corrected immutable successor manifest disagrees.",
    )
    parsed = _verify_reader(result.content, rating=1, stage="manifest revision 2")
    _require(
        parsed == result.manifest,
        "manifest revision 2",
        "public reader changed generated successor semantics.",
    )
    return result


def _supersede(
    workspace: Path,
    predecessor: AcademicResultPublicationResult,
    generated: AcademicResultManifestGenerationResult,
) -> AcademicResultPublicationResult:
    result = supersede_quillan_academic_results(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=2,
        expected_current_publication_id=predecessor.publication.publication_id,
    )
    _require(result.disposition == "created", "supersession", "successor was not created.")
    _verify_publication(
        result,
        generated,
        revision=2,
        registration_revision=2,
        supersedes=predecessor.publication.publication_id,
        stage="supersession",
    )
    replay = supersede_quillan_academic_results(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=2,
        expected_current_publication_id=predecessor.publication.publication_id,
    )
    _require(
        replay.disposition == "existing" and replay.publication == result.publication,
        "supersession",
        "exact supersession replay did not preserve Core identity.",
    )
    try:
        supersede_quillan_academic_results(
            workspace,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=2,
            expected_current_publication_id=result.publication.publication_id,
        )
    except (
        QuillanAcademicResultPublicationConflictError,
        QuillanAcademicResultPublicationIntegrityError,
    ):
        pass
    else:
        raise AcceptanceFailure("supersession", "contradictory expected head was accepted.")
    _require(
        len(
            list_publication_record_set(
                workspace,
                predecessor.publication.work,
                predecessor.publication.publication_kind,
                predecessor.publication.record_set_id,
            )
        )
        == 2,
        "supersession",
        "stale-head case created a competing publication.",
    )
    return result


def _catalog_two(workspace: Path, first: str, second: str) -> None:
    rebuild_academic_catalog(workspace)
    heads = _query(workspace, "series_heads")
    current = _query(workspace, "current")
    historical = _query(workspace, "historical")
    _require(
        len(heads) == len(current) == len(historical) == 1
        and heads[0].publication_id == current[0].publication_id == second
        and historical[0].publication_id == first
        and not heads[0].is_withdrawn
        and heads[0].is_current_selectable,
        "catalog revision 2",
        "successor catalog state disagrees.",
    )


def _historical_drift(workspace: Path, generated: AcademicResultManifestGenerationResult, publication_id: str) -> None:
    content = _core_verified(
        workspace, publication_id, generated, stage="historical source drift"
    )
    manifest = _verify_reader(content, rating=2, stage="historical source drift")
    try:
        read_authorized_academic_result_artifacts(
            workspace,
            manifest,
            REVIEWED_STUDENT_ID,
            "feedback_pdf",
            purpose=PURPOSE,
            authorization_gate=_ExactGate(manifest),
        )
    except QuillanAcademicResultArtifactIntegrityError:
        pass
    else:
        raise AcceptanceFailure(
            "historical source drift", "historical feedback silently resolved after source drift."
        )


def _withdraw(workspace: Path, publication_id: str) -> AcademicResultWithdrawalResult:
    first = withdraw_quillan_academic_result_publication(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=publication_id,
        reason=WITHDRAWAL_REASON,
    )
    replay = withdraw_quillan_academic_result_publication(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=publication_id,
        reason=WITHDRAWAL_REASON,
    )
    _require(
        first.disposition == "created"
        and replay.disposition == "existing"
        and replay.withdrawal == first.withdrawal
        and first.manifest_verification == "verified",
        "withdrawal",
        "withdrawal create/replay disagrees.",
    )
    return first


def _final_catalog(workspace: Path, first: str, second: str) -> None:
    rebuild_academic_catalog(workspace)
    current = _query(workspace, "current")
    heads = _query(workspace, "series_heads")
    historical = _query(workspace, "historical")
    withdrawn = _query(workspace, "withdrawn")
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    series = list_publication_record_set(
        workspace,
        work,
        QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
        QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    )
    _require(
        current == ()
        and len(heads) == len(historical) == len(withdrawn) == 1
        and heads[0].publication_id == withdrawn[0].publication_id == second
        and heads[0].is_series_head
        and heads[0].is_withdrawn
        and not heads[0].is_current_selectable
        and historical[0].publication_id == first
        and get_current_publication_record(
            workspace,
            work,
            QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
            QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        )
        is None
        and len(series) == 2,
        "final catalog",
        "withdrawn final catalog semantics disagree.",
    )


def _audit(workspace: Path) -> None:
    report = audit_academic_registry(
        workspace,
        options=RegistryAuditOptions(
            scopes=("registrations", "publications", "manifests", "contracts", "catalog", "locks"),
            class_id=CLASS_ID,
            module_id=QUILLAN_MODULE_ID,
            work_id=ASSIGNMENT_ID,
            require_catalog=True,
            require_producer_profiles=True,
            discover_installed_producer_profiles=True,
        ),
    )
    counts = report.counts
    _require(
        report.ok
        and report.canonical_valid
        and report.manifests_valid is True
        and report.contracts_compatible is True
        and report.catalog_ready is True
        and counts.registration_revisions == 2
        and counts.publication_records == 2
        and counts.publication_series == 1
        and counts.withdrawals == 1
        and counts.verified_manifests == 2
        and counts.error_findings == 0
        and counts.locks == 0,
        "registry audit",
        "Core registry audit did not validate the exact completed lifecycle.",
    )


def run_acceptance(
    workspace: Path,
    repository: Path,
    *,
    version: str,
    expected_core_version: str,
) -> None:
    workspace = workspace.resolve(strict=True)
    repository = repository.resolve(strict=True)
    _run_stage(
        "installed provenance",
        lambda: _installed_provenance(
            workspace, repository, version=version, core_version=expected_core_version
        ),
    )
    assignment, submission, review = _run_stage(
        "native workflow handoff", lambda: _native_handoff(workspace)
    )
    registration_one, registration_one_bytes = _run_stage(
        "academic-work registration", lambda: _register(workspace)
    )
    generated_one = _run_stage(
        "manifest revision 1",
        lambda: _manifest_one(workspace, assignment, submission, review),
    )
    manifest_one_bytes = bytes(generated_one.content)
    manifest_one = _run_stage(
        "public reader revision 1",
        lambda: _verify_reader(generated_one.content, rating=2, stage="public reader revision 1"),
    )
    _require(
        manifest_one == generated_one.manifest,
        "public reader revision 1",
        "public reader changed generated manifest semantics.",
    )
    published_one = _run_stage(
        "initial publication",
        lambda: publish_quillan_academic_results(
            workspace, CLASS_ID, ASSIGNMENT_ID, manifest_revision=1
        ),
    )
    _require(
        published_one.disposition == "created",
        "initial publication",
        "initial Core publication was not newly created.",
    )
    _verify_publication(
        published_one,
        generated_one,
        revision=1,
        registration_revision=1,
        supersedes=None,
        stage="initial publication",
    )
    publication_one_path = publication_record_path(
        workspace, published_one.publication.publication_id
    )
    publication_one_bytes = publication_one_path.read_bytes()

    def replay_publication() -> None:
        replay = publish_quillan_academic_results(
            workspace, CLASS_ID, ASSIGNMENT_ID, manifest_revision=1
        )
        _require(
            replay.disposition == "existing" and replay.publication == published_one.publication,
            "publication replay",
            "exact publication replay changed Core identity.",
        )

    _run_stage("publication replay", replay_publication)
    _run_stage(
        "catalog revision 1",
        lambda: _catalog_one(workspace, published_one.publication.publication_id),
    )
    verified_one = _run_stage(
        "Core verification revision 1",
        lambda: _core_verified(
            workspace,
            published_one.publication.publication_id,
            generated_one,
            stage="Core verification revision 1",
        ),
    )
    _require(
        _verify_reader(verified_one, rating=2, stage="Core verification revision 1")
        == manifest_one,
        "Core verification revision 1",
        "reader semantics changed over Core-verified bytes.",
    )
    _run_stage(
        "authorized artifacts revision 1",
        lambda: _artifacts(workspace, manifest_one, stage="authorized artifacts revision 1"),
    )
    registration_two, registration_two_bytes = _run_stage(
        "registration independence",
        lambda: _registration_independence(workspace, generated_one, published_one),
    )
    corrected_review = _run_stage(
        "native correction", lambda: _native_correction(workspace, review)
    )
    generated_two = _run_stage(
        "manifest revision 2",
        lambda: _manifest_two(workspace, generated_one, corrected_review),
    )
    manifest_two_bytes = bytes(generated_two.content)
    published_two = _run_stage(
        "supersession", lambda: _supersede(workspace, published_one, generated_two)
    )
    publication_two_path = publication_record_path(
        workspace, published_two.publication.publication_id
    )
    publication_two_bytes = publication_two_path.read_bytes()
    _run_stage(
        "catalog revision 2",
        lambda: _catalog_two(
            workspace,
            published_one.publication.publication_id,
            published_two.publication.publication_id,
        ),
    )
    verified_two = _run_stage(
        "Core verification revision 2",
        lambda: _core_verified(
            workspace,
            published_two.publication.publication_id,
            generated_two,
            stage="Core verification revision 2",
        ),
    )
    manifest_two = _verify_reader(
        verified_two, rating=1, stage="Core verification revision 2"
    )
    _run_stage(
        "authorized artifacts revision 2",
        lambda: _artifacts(workspace, manifest_two, stage="authorized artifacts revision 2"),
    )
    _run_stage(
        "historical source drift",
        lambda: _historical_drift(
            workspace, generated_one, published_one.publication.publication_id
        ),
    )
    withdrawal = _run_stage(
        "withdrawal",
        lambda: _withdraw(workspace, published_two.publication.publication_id),
    )
    withdrawal_path = publication_withdrawal_path(
        workspace, published_two.publication.publication_id
    )
    withdrawal_bytes = withdrawal_path.read_bytes()
    _run_stage(
        "final catalog",
        lambda: _final_catalog(
            workspace,
            published_one.publication.publication_id,
            published_two.publication.publication_id,
        ),
    )
    _run_stage("registry audit", lambda: _audit(workspace))

    def immutable() -> None:
        work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
        aliases = tuple(generated_one.path.parent / name for name in ("latest.json", "current.json"))
        _require(
            generated_one.path.read_bytes() == manifest_one_bytes
            and generated_two.path.read_bytes() == manifest_two_bytes
            and publication_one_path.read_bytes() == publication_one_bytes
            and publication_two_path.read_bytes() == publication_two_bytes
            and withdrawal_path.read_bytes() == withdrawal_bytes
            and academic_work_registration_revision_path(workspace, work, 1).read_bytes()
            == registration_one_bytes
            and academic_work_registration_revision_path(workspace, work, 2).read_bytes()
            == registration_two_bytes
            and load_academic_work_registration_revision(workspace, work, 1)
            == registration_one
            and load_current_academic_work_registration(workspace, work) == registration_two
            and not any(path.exists() for path in aliases),
            "immutability",
            "immutable history or mutable-alias boundary disagrees.",
        )
        _require(
            load_publication_withdrawal(
                workspace, published_two.publication.publication_id
            )
            == withdrawal.withdrawal,
            "immutability",
            "withdrawal is not an independent immutable record.",
        )

    _run_stage("immutability", immutable)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify installed Quillan academic-result producer lifecycle."
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--version", default="0.9.0")
    parser.add_argument("--expected-core-version", default="0.6.0")
    args = parser.parse_args()
    try:
        run_acceptance(
            args.workspace,
            args.repository,
            version=args.version,
            expected_core_version=args.expected_core_version,
        )
    except AcceptanceFailure as error:
        print(f"FAILED: {error.stage}: {error.message}", file=sys.stderr)
        return 1
    except Exception:
        print("FAILED: unexpected installed producer-acceptance harness error.", file=sys.stderr)
        return 1
    print("Installed Quillan producer acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

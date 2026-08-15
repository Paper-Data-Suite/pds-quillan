from __future__ import annotations

import inspect
from pathlib import Path

import quillan.academic_result_artifacts as artifacts
import quillan.academic_result_reader as reader


def test_pure_reader_source_has_only_contract_dependencies() -> None:
    source = Path("quillan/academic_result_reader.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in (
        "pathlib",
        "import os",
        "importlib",
        "subprocess",
        "socket",
        "requests",
        "academic_result_manifest_generation",
        "academic_result_publication",
        "feedback_export",
        "record_context",
        "publication_storage",
        "registry_services",
        "academic_catalog",
        "meridian",
        "vitrine",
        "scoreform",
        "concord",
        "portia",
    ):
        assert forbidden not in lowered
    assert "open(" not in source
    assert "read_bytes(" not in source
    assert "write_bytes(" not in source
    assert "write_text(" not in source


def test_artifact_module_has_no_core_publication_or_consumer_policy_dependency() -> None:
    source = Path("quillan/academic_result_artifacts.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in (
        "publication_storage",
        "registry_services",
        "academic_catalog",
        "query_publication_catalog",
        "publish_manifest_revision",
        "supersede_manifest_revision",
        "withdraw_publication",
        "meridian",
        "vitrine",
        "scoreform",
        "concord",
        "portia",
    ):
        assert forbidden not in lowered


def test_artifact_public_request_has_no_path_or_role_authorization_surface() -> None:
    fields = artifacts.AcademicResultArtifactAuthorizationRequest.__dataclass_fields__
    assert tuple(fields) == (
        "work",
        "record_set_id",
        "record_set_revision",
        "student_id",
        "artifact_kind",
        "purpose",
    )
    assert not {
        "path",
        "url",
        "role",
        "actor",
        "teacher",
        "admin",
        "include_private",
    }.intersection(fields)


def test_artifact_kinds_are_closed_and_no_generic_reader_is_exported() -> None:
    public = set(artifacts.__all__)
    assert "read_authorized_academic_result_artifacts" in public
    assert not {
        "read_artifact",
        "read_file",
        "open_source",
        "read_native_record",
        "read_any_artifact",
    }.intersection(public)
    rendered = str(artifacts.AcademicResultArtifactKind)
    assert "student_work" in rendered
    assert "feedback_pdf" in rendered
    assert "feedback_markdown" in rendered


def test_reader_public_surface_contains_no_consumer_selection_policy() -> None:
    forbidden = (
        "grade",
        "proficiency",
        "mastery",
        "best",
        "latest",
        "official",
        "portfolio",
        "showcase",
        "graduation",
    )
    for name in reader.__all__:
        assert not any(fragment in name.lower() for fragment in forbidden)


def test_artifact_public_function_accepts_identity_not_arbitrary_path() -> None:
    signature = inspect.signature(
        artifacts.read_authorized_academic_result_artifacts
    )
    assert tuple(signature.parameters) == (
        "workspace_root",
        "manifest",
        "student_id",
        "artifact_kind",
        "purpose",
        "authorization_gate",
    )
    assert "path" not in signature.parameters
    assert "publication_id" not in signature.parameters
    assert "source_record" not in signature.parameters


def test_reader_and_artifact_modules_define_explicit_public_surfaces() -> None:
    assert type(reader.__all__) is tuple
    assert type(artifacts.__all__) is tuple
    assert len(reader.__all__) == len(set(reader.__all__))
    assert len(artifacts.__all__) == len(set(artifacts.__all__))

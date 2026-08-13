from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tomllib
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import pytest
from pds_core.academic_work_registrations import AcademicWorkRegistration
from pds_core.module_profiles import ModuleProfile
from pds_core.publication_compatibility import (
    PUBLICATION_PRODUCER_ENTRY_POINT_GROUP,
    PublicationProducerProfile,
    PublicationProducerProfileError,
    build_publication_producer_registry,
    discover_publication_producer_profiles,
    evaluate_publication_compatibility,
    validate_publication_producer_profile,
)
from pds_core.publication_records import (
    PublicationCapability,
    PublicationRecord,
    PublicationRecordValidationError,
)
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef

from quillan.pds_module import get_module_profile
from quillan.pds_publication import get_publication_producer_profile

_SUPPORTED_CAPABILITIES = frozenset({"standards_ratings"})
_UNSUPPORTED_CAPABILITIES = frozenset(
    {
        "points",
        "question_evidence",
        "multiple_attempts",
        "criterion_scores",
        "moderated_scores",
        "intervention_history",
        "intervention_status",
        "intervention_outcomes",
    }
)
_INTERVENTION_CAPABILITIES = frozenset(
    {"intervention_history", "intervention_status", "intervention_outcomes"}
)
_NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


def _publication(
    *,
    capabilities: tuple[PublicationCapability, ...] = ("standards_ratings",),
) -> PublicationRecord:
    return PublicationRecord(
        schema_version="1",
        record_type="publication_record",
        publication_id="pub_" + "1" * 32,
        work=ModuleWorkRef("quillan", "class1", "assignment1"),
        source_record=None,
        publication_kind="academic_result_set",
        capabilities=capabilities,
        record_set_id="academic_results",
        record_set_revision=1,
        manifest_contract_version="quillan_academic_result_manifest_v1",
        manifest_path=(
            "classes/class1/modules/quillan/work/assignment1/"
            "exports/manifests/academic_results/1.json"
        ),
        manifest_digest_algorithm="sha256",
        manifest_digest="0" * 64,
        published_at=_NOW,
        academic_work_registration_revision=1,
        supersedes_publication_id=None,
    )


def _registration(
    publication: PublicationRecord,
    *,
    producer_contract_version: str = "quillan_academic_work_v1",
    work: ModuleWorkRef | None = None,
    registration_revision: int = 1,
) -> AcademicWorkRegistration:
    return AcademicWorkRegistration(
        schema_version="1",
        record_type="academic_work_registration",
        work=publication.work if work is None else work,
        registration_revision=registration_revision,
        producer_contract_version=producer_contract_version,
        title="Synthetic writing assignment",
        work_kind="assignment",
        academic_intent="summative",
        lifecycle="active",
        created_at=_NOW,
        updated_at=_NOW,
        source_records=(
            ModuleRecordRef("quillan", "assignment", "assignment1", "2"),
        ),
    )


def test_provider_returns_exact_validated_immutable_profile() -> None:
    assert tuple(inspect.signature(get_publication_producer_profile).parameters) == ()
    profile = get_publication_producer_profile()
    assert isinstance(profile, PublicationProducerProfile)
    assert validate_publication_producer_profile(profile) == profile
    assert get_publication_producer_profile() == profile
    assert profile.module_id == "quillan"
    assert profile.display_name == "Quillan"
    assert profile.supported_core_publication_schema_versions == frozenset({"1"})
    assert profile.supported_academic_work_contract_versions == frozenset(
        {"quillan_academic_work_v1"}
    )
    assert len(profile.publication_contracts) == 1
    support = profile.publication_contracts[0]
    assert support.publication_kind == "academic_result_set"
    assert support.manifest_contract_versions == frozenset(
        {"quillan_academic_result_manifest_v1"}
    )
    assert support.supported_capabilities == _SUPPORTED_CAPABILITIES
    assert support.source_record_contracts == ()
    assert support.allows_missing_source_record is True
    with pytest.raises((FrozenInstanceError, AttributeError)):
        profile.module_id = "other"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        profile.supported_core_publication_schema_versions.add("2")  # type: ignore[attr-defined]
    with pytest.raises((FrozenInstanceError, AttributeError)):
        support.publication_kind = "intervention_record_set"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        support.supported_capabilities.add("points")  # type: ignore[attr-defined]


def test_extracted_constants_preserve_previous_public_imports() -> None:
    from quillan.academic_result_manifest import (
        ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION as manifest_version,
    )
    from quillan.academic_work_registration import (
        QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION as work_version,
    )
    from quillan.pds_contract import (
        ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
        QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    )

    assert manifest_version == ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    assert work_version == QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION


def test_pyproject_declares_two_exact_independent_entry_points() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    groups = project["project"]["entry-points"]
    assert groups["paper_data_suite.modules"] == {
        "quillan": "quillan.pds_module:get_module_profile"
    }
    assert groups[PUBLICATION_PRODUCER_ENTRY_POINT_GROUP] == {
        "quillan": "quillan.pds_publication:get_publication_producer_profile"
    }


def test_installed_entry_point_discovery_and_registry_are_exact() -> None:
    points = tuple(
        metadata.entry_points().select(
            group=PUBLICATION_PRODUCER_ENTRY_POINT_GROUP,
            name="quillan",
        )
    )
    assert len(points) == 1
    point = points[0]
    assert point.value == "quillan.pds_publication:get_publication_producer_profile"
    provider = point.load()
    assert tuple(inspect.signature(provider).parameters) == ()
    assert provider() == get_publication_producer_profile()
    profiles = tuple(
        profile
        for profile in discover_publication_producer_profiles()
        if profile.module_id == "quillan"
    )
    assert profiles == (get_publication_producer_profile(),)
    assert (
        build_publication_producer_registry().get("quillan")
        == get_publication_producer_profile()
    )


def test_routing_and_publication_profiles_remain_independent() -> None:
    routing = get_module_profile()
    publication = get_publication_producer_profile()
    assert id(get_module_profile) != id(get_publication_producer_profile)
    assert isinstance(routing, ModuleProfile)
    assert isinstance(publication, PublicationProducerProfile)
    assert routing.module_id == publication.module_id == "quillan"
    assert routing.display_name == publication.display_name == "Quillan"
    assert callable(routing.route_handler)
    assert callable(routing.registration_validator)
    assert not hasattr(publication, "route_handler")
    assert not hasattr(publication, "registration_validator")
    assert not hasattr(routing, "publication_contracts")


def test_profile_exposes_no_reader_parser_generator_or_operation_callbacks() -> None:
    names = set(dir(get_publication_producer_profile()))
    assert names.isdisjoint(
        {
            "manifest_parser",
            "manifest_reader",
            "manifest_validator",
            "manifest_generator",
            "publication_callback",
            "supersession_callback",
            "withdrawal_callback",
            "route_handler",
            "registration_validator",
            "academic_work_registration_callback",
            "cli_callback",
            "menu_callback",
        }
    )


def test_exact_publication_contract_is_compatible() -> None:
    publication = _publication()
    result = evaluate_publication_compatibility(
        publication,
        get_publication_producer_profile(),
        _registration(publication),
    )
    assert result.compatible is True
    assert result.codes == ()
    assert publication.source_record is None
    assert not Path(publication.manifest_path).exists()


def test_missing_and_wrong_registration_contract_are_incompatible() -> None:
    publication = _publication()
    assert evaluate_publication_compatibility(
        publication, get_publication_producer_profile()
    ).codes == ("contracts.registration_version_incompatible",)
    assert evaluate_publication_compatibility(
        publication,
        get_publication_producer_profile(),
        _registration(publication, producer_contract_version="other_contract_v1"),
    ).codes == ("contracts.registration_version_incompatible",)


def test_registration_relationship_errors_are_invalid_evaluation_input() -> None:
    publication = _publication()
    with pytest.raises(PublicationProducerProfileError, match="work does not match"):
        evaluate_publication_compatibility(
            publication,
            get_publication_producer_profile(),
            _registration(
                publication,
                work=ModuleWorkRef("quillan", "class1", "other_assignment"),
            ),
        )
    with pytest.raises(PublicationProducerProfileError, match="revision does not match"):
        evaluate_publication_compatibility(
            publication,
            get_publication_producer_profile(),
            _registration(publication, registration_revision=2),
        )


def test_schema_manifest_kind_source_and_module_mismatches_are_rejected() -> None:
    publication = _publication()
    registration = _registration(publication)
    profile = get_publication_producer_profile()
    unsupported_schema = replace(
        profile, supported_core_publication_schema_versions=frozenset({"2"})
    )
    assert evaluate_publication_compatibility(
        publication, unsupported_schema, registration
    ).codes == ("contracts.publication_schema_incompatible",)
    assert evaluate_publication_compatibility(
        replace(publication, manifest_contract_version="fictional_manifest_v1"),
        profile,
        registration,
    ).codes == ("contracts.manifest_version_incompatible",)
    intervention = replace(
        publication,
        publication_kind="intervention_record_set",
        capabilities=("intervention_status",),
        academic_work_registration_revision=None,
    )
    assert evaluate_publication_compatibility(intervention, profile).codes == (
        "contracts.publication_kind_incompatible",
    )
    for source in (
        ModuleRecordRef("quillan", "assignment", "assignment1", "2"),
        ModuleRecordRef("quillan", "review", "review1", "2"),
    ):
        assert evaluate_publication_compatibility(
            replace(publication, source_record=source), profile, registration
        ).codes == ("contracts.source_record_kind_incompatible",)
    with pytest.raises(
        PublicationRecordValidationError,
        match="source_record.module_id must match work.module_id",
    ):
        replace(
            publication,
            source_record=ModuleRecordRef(
                "other", "assignment", "assignment1", "2"
            ),
        )
    assert evaluate_publication_compatibility(
        publication, replace(profile, module_id="other"), registration
    ).codes == ("contracts.profile_module_mismatch",)


@pytest.mark.parametrize(
    "capability", sorted(_UNSUPPORTED_CAPABILITIES - _INTERVENTION_CAPABILITIES)
)
def test_unsupported_capabilities_are_incompatible(
    capability: PublicationCapability,
) -> None:
    publication = _publication(capabilities=(capability,))
    result = evaluate_publication_compatibility(
        publication,
        get_publication_producer_profile(),
        _registration(publication),
    )
    assert result.codes == ("contracts.capability_incompatible",)


@pytest.mark.parametrize("capability", sorted(_INTERVENTION_CAPABILITIES))
def test_core_rejects_intervention_capabilities_on_academic_results(
    capability: PublicationCapability,
) -> None:
    with pytest.raises(
        PublicationRecordValidationError,
        match="academic-result publications cannot claim intervention capabilities",
    ):
        _publication(capabilities=(capability,))


def test_profile_advertises_no_planned_or_fictional_contracts() -> None:
    profile = get_publication_producer_profile()
    support = profile.publication_contracts[0]
    assert support.supported_capabilities.isdisjoint(_UNSUPPORTED_CAPABILITIES)
    assert profile.supported_core_publication_schema_versions == frozenset({"1"})
    assert profile.supported_academic_work_contract_versions == frozenset(
        {"quillan_academic_work_v1"}
    )
    assert support.manifest_contract_versions == frozenset(
        {"quillan_academic_result_manifest_v1"}
    )


def test_isolated_discovery_creates_no_state_or_workflow_imports(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "nonexistent_workspace"
    script = """
import json
import os
import pathlib
import sys
from pds_core.publication_compatibility import (
    build_publication_producer_registry,
    discover_publication_producer_profiles,
)
from quillan.pds_publication import get_publication_producer_profile

workspace = pathlib.Path(os.environ["PDS_WORKSPACE_ROOT"])
direct = get_publication_producer_profile()
discovered = [p for p in discover_publication_producer_profiles() if p.module_id == "quillan"]
registry = build_publication_producer_registry()
blocked = ("scoreform", "concord", "portia", "pds_meridian", "vitrine")
workflow_modules = (
    "quillan.academic_result_manifest",
    "quillan.academic_result_manifest_generation",
    "quillan.academic_work_registration",
    "quillan.cli",
    "quillan.route_handler",
)
print(json.dumps({
    "direct": direct.module_id,
    "discovered": len(discovered),
    "registry": registry.get("quillan").module_id,
    "workspace_exists": workspace.exists(),
    "blocked_imports": sorted(name for name in sys.modules if name.split(".")[0] in blocked),
    "workflow_imports": sorted(name for name in workflow_modules if name in sys.modules),
}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=Path.cwd(),
        env={"PDS_WORKSPACE_ROOT": str(workspace)},
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "direct": "quillan",
        "discovered": 1,
        "registry": "quillan",
        "workspace_exists": False,
        "blocked_imports": [],
        "workflow_imports": [],
    }
    assert not workspace.exists()

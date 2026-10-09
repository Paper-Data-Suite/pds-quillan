"""Core 0.6.5 producer reader metadata: exact declared contract, not lockstep."""

from __future__ import annotations

import builtins
from dataclasses import replace
from pathlib import Path
import tomllib
from typing import Any

import pytest
from packaging.requirements import Requirement
from pds_core.publication_compatibility import (
    PublicationReaderSupport,
    evaluate_publication_compatibility,
    lookup_publication_reader_support,
    validate_publication_producer_profile,
)

from quillan.academic_result_reader import (
    QuillanAcademicResultReaderValidationError,
    read_academic_result_manifest,
)
from quillan.pds_contract import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_RESULT_READER_CONTRACT_VERSION,
)
from quillan.pds_publication import get_publication_producer_profile
from tests.test_publication_producer_profile import _publication, _registration


EXPECTED_READER = PublicationReaderSupport(
    manifest_contract_version="quillan_academic_result_manifest_v1",
    distribution_name="quillan",
    reader_contract_version="quillan_academic_result_reader_v1",
)
FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "publication"
    / "quillan_academic_result_manifest_v1.json"
)


def test_exact_reader_support_survives_core_validation_and_lookup() -> None:
    profile = get_publication_producer_profile()
    assert QUILLAN_ACADEMIC_RESULT_READER_CONTRACT_VERSION == (
        "quillan_academic_result_reader_v1"
    )
    assert ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION == (
        "quillan_academic_result_manifest_v1"
    )
    assert profile.publication_contracts[0].reader_support == (EXPECTED_READER,)
    assert lookup_publication_reader_support(
        profile, "academic_result_set", ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    ) == EXPECTED_READER
    validated = validate_publication_producer_profile(profile)
    assert validated == profile
    assert validated is not profile
    assert lookup_publication_reader_support(
        validated, "academic_result_set", ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    ) == EXPECTED_READER
    assert lookup_publication_reader_support(
        profile, "academic_result_set", "future_manifest_v2"
    ) is None
    assert lookup_publication_reader_support(
        profile, "intervention_record_set", ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    ) is None


def test_publication_compatibility_is_independent_of_reader_declaration() -> None:
    profile = get_publication_producer_profile()
    old_style = replace(
        profile,
        publication_contracts=(
            replace(profile.publication_contracts[0], reader_support=()),
        ),
    )
    publication = _publication()
    registration = _registration(publication)
    assert evaluate_publication_compatibility(
        publication, profile, registration
    ) == evaluate_publication_compatibility(publication, old_style, registration)
    assert evaluate_publication_compatibility(publication, profile).codes == (
        "contracts.registration_version_incompatible",
    )


def test_provider_does_not_import_or_invoke_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("quillan.academic_result_reader"):
            raise AssertionError("Profile construction must not import reader.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    profile = get_publication_producer_profile()
    assert profile.publication_contracts[0].reader_support == (EXPECTED_READER,)
    assert lookup_publication_reader_support(
        profile, "academic_result_set", ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    ) == EXPECTED_READER


def test_declared_public_reader_remains_canonical_and_pure() -> None:
    canonical = FIXTURE.read_bytes()
    original = bytes(canonical)
    result = read_academic_result_manifest(canonical)
    assert result.contract_version == ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
    assert canonical == original
    with pytest.raises(QuillanAcademicResultReaderValidationError):
        read_academic_result_manifest(canonical + b" ")


def test_core_floor_is_explicit_without_any_sibling_dependency() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    dependencies = [Requirement(value) for value in project["dependencies"]]
    core = [value for value in dependencies if value.name == "pds-core"]
    assert len(core) == 1
    assert str(core[0].specifier) in {">=0.6.5,<0.7", "<0.7,>=0.6.5"}
    assert {value.name for value in dependencies}.isdisjoint(
        {"pds-meridian", "pds-vitrine", "meridian", "vitrine"}
    )
